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
const statusJobId = document.getElementById("status-job-id");
const taskFilename = document.getElementById("task-filename");
const taskProgressText = document.getElementById("task-progress-text");
const taskProgressBar = document.getElementById("task-progress-bar");
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

const artifactNameElements = {
  json: document.getElementById("artifact-json-name"),
  srt: document.getElementById("artifact-srt-name"),
  text: document.getElementById("artifact-text-name"),
  video: document.getElementById("artifact-video-name"),
};

const defaultArtifactNames = {
  json: "transcript.json",
  srt: "subtitle.srt",
  text: "transcript.txt",
  video: "output_subtitled.mp4",
};

const statusTextMap = {
  idle: "\u7A7A\u95F2",
  queued: "\u6392\u961F\u4E2D",
  running: "\u5904\u7406\u4E2D",
  succeeded: "\u5DF2\u5B8C\u6210",
  failed: "\u5931\u8D25",
};

const stepLabelMap = {
  waiting: "\u7B49\u5F85\u4E0A\u4F20",
  queued: "\u8FDB\u5165\u961F\u5217",
  starting: "\u51C6\u5907\u5904\u7406",
  processing: "\u5904\u7406\u4E2D",
  transcribing: "\u8BED\u97F3\u8F6C\u5199",
  extracting: "\u63D0\u53D6\u97F3\u9891",
  transcript: "\u751F\u6210\u8F6C\u5199",
  rendering: "\u6E32\u67D3\u5B57\u5E55",
  burn_subtitles: "\u70E7\u5F55\u5B57\u5E55",
  done: "\u5904\u7406\u5B8C\u6210",
  failed: "\u5904\u7406\u5931\u8D25",
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

for (const input of document.querySelectorAll('input[name="subtitlePosition"]')) {
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
    setIdleState("\u8BF7\u5148\u9009\u62E9\u4E00\u4E2A\u97F3\u9891\u6216\u89C6\u9891\u6587\u4EF6\u3002");
    return;
  }

  const formData = new FormData(form);
  lockForm(true);
  setRunningState({
    title: "\u6587\u4EF6\u5DF2\u4E0A\u4F20",
    status: "running",
    message: "\u5DF2\u521B\u5EFA\u4EFB\u52A1\uFF0C\u6B63\u5728\u51C6\u5907\u63D0\u53D6\u97F3\u9891\u548C\u751F\u6210\u5B57\u5E55\u3002",
    step: "queued",
    filename: audioInput.files[0].name,
    jobId: currentJobId,
  });
  applyArtifacts({});

  try {
    const response = await fetch("/api/jobs", {
      method: "POST",
      body: formData,
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "\u521B\u5EFA\u4EFB\u52A1\u5931\u8D25\u3002");
    }
    currentJobId = payload.jobId;
    updateFromJob(payload);
    startPolling(payload.jobId);
  } catch (error) {
    setFailedState(error.message || "\u4E0A\u4F20\u5931\u8D25\u3002");
    lockForm(false);
  }
});

function syncFileState() {
  const file = audioInput.files?.[0];
  if (!file) {
    fileChip.textContent = "\u6682\u672A\u9009\u62E9\u6587\u4EF6";
    taskFilename.textContent = "\u672A\u9009\u62E9\u6587\u4EF6";
    return;
  }
  const sizeInMb = (file.size / 1024 / 1024).toFixed(2);
  fileChip.textContent = `${file.name} \u00B7 ${sizeInMb} MB`;
  taskFilename.textContent = file.name;
}

function updateSampleSubtitle() {
  const size = Number(fontSizeInput.value || 24);
  const position = document.querySelector('input[name="subtitlePosition"]:checked')?.value || "bottom";
  sampleSubtitle.style.fontSize = `${size}px`;
  sampleSubtitle.classList.remove("is-top", "is-middle", "is-bottom");
  sampleSubtitle.classList.add(`is-${position}`);
}

function lockForm(locked) {
  submitButton.disabled = locked;
  audioInput.disabled = locked;
  fontSizeInput.disabled = locked;
  for (const input of document.querySelectorAll('input[name="subtitlePosition"]')) {
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
        throw new Error(payload.detail || "\u83B7\u53D6\u4EFB\u52A1\u72B6\u6001\u5931\u8D25\u3002");
      }
      updateFromJob(payload);
      if (payload.status === "succeeded" || payload.status === "failed") {
        stopPolling();
        lockForm(false);
      }
    } catch (error) {
      stopPolling();
      lockForm(false);
      setFailedState(error.message || "\u8F6E\u8BE2\u4EFB\u52A1\u72B6\u6001\u5931\u8D25\u3002");
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
  const step = String(job.step || "processing").toLowerCase();
  const message = job.error || job.message || "\u5904\u7406\u4E2D";
  const filename = job.filename || audioInput.files?.[0]?.name || "\u672A\u547D\u540D\u6587\u4EF6";
  const progress = computeProgress(step, status);

  statusJobId.textContent = job.jobId || currentJobId || "-";
  taskFilename.textContent = filename;
  applyProgress(progress);

  if (status === "succeeded") {
    statusTitle.textContent = "\u5B57\u5E55\u751F\u6210\u5B8C\u6210";
    statusPill.textContent = statusTextMap.succeeded;
    statusPill.className = "status-pill succeeded";
    statusMessage.textContent = message;
    statusStep.textContent = formatStep(step);
    applyTimeline(step, status);
    applyArtifacts(job.artifacts || {});
    showVideo(job.artifacts?.video || "");
    artifactCopy.textContent = "\u7ED3\u679C\u5DF2\u751F\u6210\uFF0C\u53EF\u76F4\u63A5\u4E0B\u8F7D\u5B57\u5E55\u6587\u4EF6\u548C\u89C6\u9891\u3002";
    return;
  }

  if (status === "failed") {
    setFailedState(message, step);
    applyArtifacts(job.artifacts || {});
    return;
  }

  setRunningState({
    title: progress > 0 ? "\u4EFB\u52A1\u5904\u7406\u4E2D" : "\u7B49\u5F85\u5F00\u59CB",
    status,
    message,
    step,
    filename,
    jobId: job.jobId || currentJobId,
  });
  applyArtifacts(job.artifacts || {});
}

function setIdleState(message) {
  statusTitle.textContent = "\u7B49\u5F85\u4E0A\u4F20\u6587\u4EF6";
  statusPill.textContent = statusTextMap.idle;
  statusPill.className = "status-pill idle";
  statusMessage.textContent = message;
  statusStep.textContent = formatStep("waiting");
  statusJobId.textContent = "-";
  taskProgressText.textContent = "0%";
  taskProgressBar.style.width = "0%";
  artifactCopy.textContent = "\u6587\u4EF6\u751F\u6210\u540E\u4F1A\u81EA\u52A8\u70B9\u4EAE\u4E0B\u8F7D\u5165\u53E3\u3002";
  applyTimeline("waiting", "idle");
}

function setRunningState({ title, status, message, step, filename, jobId }) {
  const progress = computeProgress(step, status);
  statusTitle.textContent = title;
  statusPill.textContent = statusTextMap[status] || statusTextMap.running;
  statusPill.className = "status-pill running";
  statusMessage.textContent = message;
  statusStep.textContent = formatStep(step);
  statusJobId.textContent = jobId || currentJobId || "-";
  taskFilename.textContent = filename || taskFilename.textContent;
  applyProgress(progress);
  artifactCopy.textContent = "\u4EFB\u52A1\u6267\u884C\u4E2D\uFF0C\u5B8C\u6210\u540E\u53EF\u4E0B\u8F7D\u6240\u6709\u4EA7\u7269\u3002";
  applyTimeline(step, status);
  hideVideo();
}

function setFailedState(message, step = "failed") {
  statusTitle.textContent = "\u4EFB\u52A1\u5904\u7406\u5931\u8D25";
  statusPill.textContent = statusTextMap.failed;
  statusPill.className = "status-pill failed";
  statusMessage.textContent = message;
  statusStep.textContent = formatStep(step);
  applyProgress(computeProgress(step, "failed"));
  artifactCopy.textContent = "\u5F53\u524D\u4EFB\u52A1\u672A\u6210\u529F\u5B8C\u6210\uFF0C\u8BF7\u68C0\u67E5\u9519\u8BEF\u4FE1\u606F\u540E\u91CD\u8BD5\u3002";
  applyTimeline(step, "failed");
  hideVideo();
}

function applyTimeline(step, status) {
  const items = Array.from(timeline.querySelectorAll(".timeline-item"));
  const stepText = String(step || "").toLowerCase();
  const activeIndex = stepText.includes("render") || stepText.includes("burn") || stepText.includes("video")
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
    const nameElement = artifactNameElements[key];
    if (url) {
      element.href = url;
      element.classList.remove("disabled");
      nameElement.textContent = defaultArtifactNames[key];
    } else {
      element.href = "#";
      element.classList.add("disabled");
      nameElement.textContent = defaultArtifactNames[key];
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

function computeProgress(step, status) {
  if (status === "succeeded") {
    return 100;
  }
  if (status === "failed") {
    return 100;
  }
  const stepText = String(step || "").toLowerCase();
  if (stepText.includes("render") || stepText.includes("burn") || stepText.includes("video")) {
    return 80;
  }
  if (stepText.includes("trans") || stepText.includes("json") || stepText.includes("text") || stepText.includes("extract")) {
    return 55;
  }
  if (stepText.includes("start") || stepText.includes("queue")) {
    return 20;
  }
  return 10;
}

function applyProgress(progress) {
  const safeProgress = Math.max(0, Math.min(100, Number(progress) || 0));
  taskProgressText.textContent = `${safeProgress}%`;
  taskProgressBar.style.width = `${safeProgress}%`;
}

function formatStep(step) {
  return stepLabelMap[step] || step || "\u5904\u7406\u4E2D";
}

setIdleState("\u4E0A\u4F20\u6587\u4EF6\u540E\u5C06\u81EA\u52A8\u5F00\u59CB\u8F6C\u5199\u5E76\u751F\u6210\u5B57\u5E55\u3002");
syncFileState();
updateSampleSubtitle();
