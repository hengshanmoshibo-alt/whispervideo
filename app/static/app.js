const form = document.getElementById("job-form");
const audioInput = document.getElementById("audio-input");
const dropzone = document.getElementById("dropzone");
const fileChip = document.getElementById("file-chip");
const fontSizeInput = document.getElementById("font-size-input");
const fontSizeValue = document.getElementById("font-size-value");
const submitButton = document.getElementById("submit-button");

const statusTitle = document.getElementById("status-title");
const statusPill = document.getElementById("status-pill");
const statusMessage = document.getElementById("status-message");
const statusStep = document.getElementById("status-step");
const timeline = document.getElementById("timeline");

const previewVideo = document.getElementById("preview-video");
const screenFrame = document.getElementById("screen-frame");
const emptyState = document.getElementById("empty-state");
const artifactCopy = document.getElementById("artifact-copy");
const sampleSubtitle = document.getElementById("sample-subtitle");

const artifactLinks = {
  json: document.getElementById("artifact-json"),
  srt: document.getElementById("artifact-srt"),
  text: document.getElementById("artifact-text"),
  video: document.getElementById("artifact-video"),
};

const statusTextMap = {
  idle: "空闲",
  queued: "排队中",
  running: "处理中",
  succeeded: "已完成",
  failed: "失败",
};

let pollTimer = null;
let currentJobId = null;

fontSizeInput.addEventListener("input", () => {
  fontSizeValue.textContent = fontSizeInput.value;
  updateSampleSubtitle();
});

audioInput.addEventListener("change", () => {
  syncFileState();
});

for (const input of form.querySelectorAll('input[name="subtitlePosition"]')) {
  input.addEventListener("change", () => {
    updateSampleSubtitle();
  });
}

["dragenter", "dragover"].forEach((eventName) => {
  dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropzone.classList.add("dragover");
  });
});

["dragleave", "drop"].forEach((eventName) => {
  dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    if (eventName === "drop" && event.dataTransfer?.files?.length) {
      audioInput.files = event.dataTransfer.files;
      syncFileState();
    }
    dropzone.classList.remove("dragover");
  });
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!audioInput.files?.length) {
    setIdleState("请先选择一个音频或视频文件。");
    return;
  }

  const formData = new FormData(form);
  lockForm(true);
  setRunningState({
    title: "正在提交任务",
    status: "running",
    message: "上传任务已提交，正在等待后端接收。",
    step: "queued",
  });
  applyArtifacts({});

  try {
    const response = await fetch("/api/jobs", {
      method: "POST",
      body: formData,
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "创建任务失败。");
    }
    currentJobId = payload.jobId;
    updateFromJob(payload);
    startPolling(payload.jobId);
  } catch (error) {
    setFailedState(error.message || "上传失败。");
    lockForm(false);
  }
});

function syncFileState() {
  const file = audioInput.files?.[0];
  if (!file) {
    fileChip.textContent = "尚未选择文件";
    return;
  }
  const sizeInMb = (file.size / 1024 / 1024).toFixed(2);
  fileChip.textContent = `${file.name} · ${sizeInMb} MB`;
}

function updateSampleSubtitle() {
  const size = Number(fontSizeInput.value || 32);
  const position = form.querySelector('input[name="subtitlePosition"]:checked')?.value || "bottom";
  sampleSubtitle.style.fontSize = `${size}px`;
  sampleSubtitle.classList.remove("is-top", "is-middle", "is-bottom");
  sampleSubtitle.classList.add(`is-${position}`);
}

function lockForm(locked) {
  submitButton.disabled = locked;
  audioInput.disabled = locked;
  fontSizeInput.disabled = locked;
  for (const input of form.querySelectorAll('input[name="subtitlePosition"]')) {
    input.disabled = locked;
  }
}

function startPolling(jobId) {
  stopPolling();
  pollTimer = window.setInterval(async () => {
    try {
      const response = await fetch(`/api/jobs/${jobId}`);
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || "获取任务状态失败。");
      }
      updateFromJob(payload);
      if (payload.status === "succeeded" || payload.status === "failed") {
        stopPolling();
        lockForm(false);
      }
    } catch (error) {
      stopPolling();
      lockForm(false);
      setFailedState(error.message || "轮询任务失败。");
    }
  }, 2000);
}

function stopPolling() {
  if (pollTimer !== null) {
    window.clearInterval(pollTimer);
    pollTimer = null;
  }
}

function updateFromJob(job) {
  const status = job.status || "running";
  const step = job.step || "processing";
  const message = job.error || job.message || "处理中";

  if (status === "succeeded") {
    statusTitle.textContent = "";
    statusPill.textContent = statusTextMap.succeeded;
    statusPill.className = "status-pill succeeded";
    statusMessage.textContent = message;
    statusStep.textContent = step;
    applyTimeline(step, status);
    applyArtifacts(job.artifacts || {});
    showVideo(job.artifacts?.video || "");
    artifactCopy.textContent = "";
    return;
  }

  if (status === "failed") {
    setFailedState(message, step);
    applyArtifacts(job.artifacts || {});
    return;
  }

  setRunningState({
    title: "处理中",
    status,
    message,
    step,
  });
  applyArtifacts(job.artifacts || {});
}

function setIdleState(message) {
  statusTitle.textContent = "等待上传";
  statusPill.textContent = statusTextMap.idle;
  statusPill.className = "status-pill idle";
  statusMessage.textContent = message;
  statusStep.textContent = "等待中";
  applyTimeline("waiting", "idle");
}

function setRunningState({ title, status, message, step }) {
  statusTitle.textContent = title;
  statusPill.textContent = statusTextMap[status] || statusTextMap.running;
  statusPill.className = "status-pill running";
  statusMessage.textContent = message;
  statusStep.textContent = step;
  artifactCopy.textContent = "";
  applyTimeline(step, status);
  hideVideo();
}

function setFailedState(message, step = "failed") {
  statusTitle.textContent = "任务失败";
  statusPill.textContent = statusTextMap.failed;
  statusPill.className = "status-pill failed";
  statusMessage.textContent = message;
  statusStep.textContent = step;
  artifactCopy.textContent = "";
  applyTimeline(step, "failed");
  hideVideo();
}

function applyTimeline(step, status) {
  const items = Array.from(timeline.querySelectorAll(".timeline-item"));
  const stepText = String(step || "").toLowerCase();
  const activeIndex = stepText.includes("render") || stepText.includes("burn")
    ? 2
    : stepText.includes("trans") || stepText.includes("json") || stepText.includes("text") || stepText.includes("extract")
      ? 1
      : 0;

  items.forEach((item, index) => {
    item.classList.remove("active", "done");
    if (status === "succeeded") {
      item.classList.add("done");
      return;
    }
    if (index < activeIndex) {
      item.classList.add("done");
    } else if (index === activeIndex) {
      item.classList.add("active");
    }
  });
}

function applyArtifacts(artifacts) {
  for (const [key, element] of Object.entries(artifactLinks)) {
    const url = artifacts[key];
    if (url) {
      element.href = url;
      element.classList.remove("disabled");
    } else {
      element.href = "#";
      element.classList.add("disabled");
    }
  }
}

function showVideo(url) {
  if (!url) {
    hideVideo();
    return;
  }
  screenFrame.classList.add("ready");
  screenFrame.classList.remove("empty");
  previewVideo.src = url;
  emptyState.style.display = "none";
}

function hideVideo() {
  screenFrame.classList.remove("ready");
  screenFrame.classList.add("empty");
  previewVideo.removeAttribute("src");
  previewVideo.load();
  emptyState.style.display = "";
}

setIdleState("选择文件后开始生成任务。");
syncFileState();
updateSampleSubtitle();
