document.addEventListener("DOMContentLoaded", () => {
  const readerId = "reader";
  const statusLabel = document.getElementById("scanner-status");
  const restartButton = document.getElementById("scan-again");
  const startButton = document.getElementById("start-scan");
  const stopButton = document.getElementById("stop-scan");
  const uploadButton = document.getElementById("upload-btn");
  const fileInput = document.getElementById("qr-image");
  const previewImage = document.getElementById("image-preview");
  const previewPlaceholder = document.querySelector(".preview-placeholder");
  const resultHeadline = document.getElementById("result-headline");
  const resultSummary = document.getElementById("result-summary");
  const resultDetails = document.getElementById("result-details");
  const resultBadge = document.getElementById("result-badge");
  const modalEl = document.getElementById("scanResultModal");
  const modalTitle = document.getElementById("result-modal-title");
  const modalStatus = document.getElementById("modal-status");
  const modalDetails = document.getElementById("modal-details");
  const modalScanAgain = document.getElementById("modal-scan-again");
  const modalInstance = new bootstrap.Modal(modalEl);

  let html5Qr = null;
  let scanning = false;
  let lastPreviewUrl = null;

  const scanConfig = {
    fps: 12,
    qrbox: { width: 280, height: 280 },
    aspectRatio: 1,
  };

  const updateStatus = (message, tone = "muted") => {
    if (!statusLabel) return;
    statusLabel.textContent = message;
    statusLabel.className = `fw-semibold text-${tone}`;
  };

  const resetControls = () => {
    startButton.disabled = scanning;
    stopButton.disabled = !scanning;
    restartButton.disabled = true;
  };

  const enableScanAgain = () => {
    restartButton.disabled = false;
  };

  const presentResult = (isReal, payload = {}) => {
    const badgeClass = isReal ? "bg-success" : "bg-danger";
    const titleText = isReal ? "✅ Real Medicine" : "❌ Fake Medicine";
    const summaryText = isReal
      ? "This batch is registered and safe to dispense."
      : "The scanned token does not exist in the registry.";

    const detailMarkup = isReal
      ? `
        <p class="mb-1"><strong>Medicine:</strong> ${payload.name}</p>
        <p class="mb-1"><strong>Batch ID:</strong> ${payload.batch_number}</p>
        <p class="mb-1"><strong>Manufacturer:</strong> ${payload.manufacturer}</p>
        <p class="mb-1"><strong>Manufacturing Date:</strong> ${payload.manufacturing_date}</p>
        <p class="mb-1"><strong>Expiry:</strong> ${payload.expiry_date}</p>
      `
      : `<p class="mb-0 text-danger">Suspicious batch detected. Please report the supplier.</p>`;

    resultBadge.textContent = isReal ? "REAL" : "FAKE";
    resultBadge.className = `badge ${badgeClass} text-white`;
    resultHeadline.textContent = titleText;
    resultSummary.textContent = summaryText;
    resultDetails.innerHTML = detailMarkup;

    modalTitle.textContent = titleText;
    modalStatus.textContent = isReal ? "Authentication successful" : "Authentication failed";
    modalDetails.innerHTML = detailMarkup;

    modalInstance.show();
    enableScanAgain();
  };

  const parseToken = (decoded) => {
    if (!decoded) return "";
    const trimmed = decoded.trim();
    if (!trimmed) return "";
    return trimmed.split("\n")[0].trim();
  };

  const ensureScanner = () => {
    if (!html5Qr) {
      html5Qr = new Html5Qrcode(readerId, {
        formatsToSupport: [Html5QrcodeSupportedFormats.QR_CODE],
        verbose: false,
      });
    }
    return html5Qr;
  };

  const stopCamera = () => {
    if (!html5Qr) {
      scanning = false;
      resetControls();
      return Promise.resolve();
    }
    return html5Qr
      .stop()
      .catch(() => Promise.resolve())
      .finally(() => {
        scanning = false;
        resetControls();
      });
  };

  const handleDetection = (decoded) => {
    scanning = false;
    stopCamera().finally(() => verifyToken(parseToken(decoded)));
  };

  const verifyToken = async (token) => {
    if (!token) {
      updateStatus("Could not decode token. Please scan again.", "danger");
      enableScanAgain();
      return;
    }

    updateStatus("Verifying token against the registry...", "info");

    try {
      const response = await fetch("/api/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ qr_data: token }),
      });
      const data = await response.json();

      if (data.status === "real") {
        presentResult(true, data.data);
        updateStatus("Batch verified. Ready for next scan.", "success");
      } else {
        presentResult(false);
        updateStatus("Fake batch detected. Please alert quality control.", "danger");
      }
    } catch (error) {
      console.error(error);
      updateStatus("Verification failed. Try again or refresh.", "danger");
    }
  };

  const startScanner = async () => {
    if (scanning) return;
    updateStatus("Detecting camera...", "info");
    resetControls();

    try {
      const scanner = ensureScanner();
      const cameras = await Html5Qrcode.getCameras();
      if (!cameras || cameras.length === 0) {
        throw new Error("No camera devices detected.");
      }
      const preferred = cameras.find((cam) => /rear|back/i.test(cam.label)) || cameras[0];
      scanning = true;
      resetControls();
      await scanner.start(
        { deviceId: { exact: preferred.id } },
        scanConfig,
        handleDetection,
        () => updateStatus("Scanning... hold the QR steady in the finder.", "muted")
      );
      updateStatus("Camera active. Align the QR code inside the frame.", "success");
    } catch (error) {
      console.error(error);
      updateStatus(error.message || "Unable to access camera.", "danger");
      scanning = false;
      resetControls();
    }
  };

  const scanImageFile = (file) => {
    if (!file) return;
    updateStatus("Scanning uploaded image...", "info");
    resetPreview();
    const reader = new FileReader();
    reader.onload = () => {
      previewImage.src = reader.result;
      previewPlaceholder.style.display = "none";
      lastPreviewUrl = reader.result;
      const image = new Image();
      image.onload = () => {
        const canvas = document.createElement("canvas");
        canvas.width = image.width;
        canvas.height = image.height;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(image, 0, 0);
        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const code = jsQR(imageData.data, canvas.width, canvas.height);
        if (code && code.data) {
          handleDetection(code.data);
        } else {
          updateStatus("No QR code found in that image.", "danger");
          enableScanAgain();
        }
      };
      image.onerror = () => {
        updateStatus("Unable to read the uploaded image.", "danger");
        enableScanAgain();
      };
      image.src = reader.result;
    };
    reader.onerror = () => {
      updateStatus("Unable to load the selected file.", "danger");
      enableScanAgain();
    };
    reader.readAsDataURL(file);
  };

  const resetPreview = () => {
    if (lastPreviewUrl) {
      URL.revokeObjectURL(lastPreviewUrl);
      lastPreviewUrl = null;
    }
    previewImage.removeAttribute("src");
    previewPlaceholder.style.display = "block";
  };

  startButton.addEventListener("click", () => {
    startScanner();
  });

  stopButton.addEventListener("click", () => {
    stopCamera().then(() => updateStatus("Camera stopped.", "muted"));
  });

  restartButton.addEventListener("click", () => {
    resetPreview();
    updateStatus("Restarting scanner...", "info");
    startScanner();
  });

  uploadButton.addEventListener("click", () => {
    fileInput.click();
  });

  fileInput.addEventListener("change", (event) => {
    const file = event.target.files && event.target.files[0];
    if (file) {
      scanImageFile(file);
    }
  });

  modalScanAgain.addEventListener("click", () => {
    modalInstance.hide();
    resetPreview();
    updateStatus("Ready for a new scan.", "info");
    startScanner();
  });

  window.addEventListener("beforeunload", () => {
    stopCamera();
  });

  resetControls();
});
