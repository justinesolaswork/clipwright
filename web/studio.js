"use strict";
const $ = id => document.getElementById(id);
const fields = ["topic", "tts", "voice", "rate", "model", "gpu_layers", "n_ctx", "accent", "fps",
  "theme", "font_style", "bg_effect", "text_anim", "caption_style", "caption_anim", "transition", "camera_style",
  "motion", "talking", "avatar_style", "avatar_color", "avatar_accessory", "avatar_size", "avatar_eyes", "avatar_antenna",
  "avatar_position", "avatar_move", "avatar_body_color", "avatar_cheeks", "avatar_body_follow",
  "bgm", "bgm_volume", "target_scenes", "render_quality", "auto_images", "web_search"];
const numeric = new Set(["rate", "gpu_layers", "n_ctx", "fps", "avatar_size", "bgm_volume", "target_scenes"]);
const flags = new Set(["talking", "auto_images", "web_search", "avatar_cheeks", "avatar_body_follow"]);
const jobButtons = ["render", "play", "generate", "motion-preview", "collect-images", "revise-btn", "download-model-btn"];
const rates = { Calm: 155, Hyped: 185, Deadpan: 165 };
let state, selected = 0, busy = false, timer, previewVersion = 0, previewUrl;
let voiceChoices = {}, kokoroReady = false, edgeReady = false, installedModels = [], modelCatalog = [], musicTracks = [], chatHistory = [], undoStack = [];

function updateMusicChoices() {
  const sel = $("bgm");
  if (!sel) return;
  sel.replaceChildren(new Option("No background music", "none"));
  musicTracks.forEach(item => {
    sel.add(new Option(item.name, item.id));
  });
  if (!musicTracks.some(item => item.id === state.bgm)) state.bgm = "none";
  sel.value = state.bgm;
}

function updateModelChoices() {
  const sel = $("model-select");
  if (!sel) return;
  sel.replaceChildren();
  installedModels.forEach(p => {
    const label = p.split(/[\\/]/).pop().replace(/\.gguf$/i, "");
    sel.add(new Option(label, p));
  });
  sel.add(new Option("Custom path…", "__custom__"));
  sel.value = installedModels.includes(state.model) ? state.model : "__custom__";
  const dlSel = $("download-model-key");
  if (dlSel) {
    dlSel.replaceChildren();
    modelCatalog.forEach(item => {
      dlSel.add(new Option(item.installed ? `${item.name} ✓ installed` : item.name, item.key));
    });
    const firstMissing = modelCatalog.find(item => !item.installed);
    if (firstMissing) dlSel.value = firstMissing.key;
  }
}

const AVATAR_PRESETS = {
  "Classic Bot": {avatar_style: "round", avatar_color: "#F4F1EA", avatar_accessory: "none", avatar_eyes: "round", avatar_antenna: "ball", avatar_cheeks: false, avatar_body_follow: true},
  "Cyber Cat": {avatar_style: "cat", avatar_color: "#70CFFF", avatar_accessory: "headphones", avatar_eyes: "wide", avatar_antenna: "bolt", avatar_cheeks: false, avatar_body_follow: true},
  "Cool Bunny": {avatar_style: "bunny", avatar_color: "#FFD6E8", avatar_accessory: "sunglasses", avatar_eyes: "happy", avatar_antenna: "none", avatar_cheeks: true, avatar_body_follow: true},
  "Party Bear": {avatar_style: "bear", avatar_color: "#C9925B", avatar_accessory: "party", avatar_eyes: "happy", avatar_antenna: "none", avatar_cheeks: true, avatar_body_follow: false, avatar_body_color: "#E85D75"},
  "Royal Robot": {avatar_style: "square", avatar_color: "#FFE9A8", avatar_accessory: "crown", avatar_eyes: "star", avatar_antenna: "double", avatar_cheeks: false, avatar_body_follow: true},
  "Sleepy Cap": {avatar_style: "round", avatar_color: "#B8E0FF", avatar_accessory: "cap", avatar_eyes: "sleepy", avatar_antenna: "ball", avatar_cheeks: false, avatar_body_follow: true},
  "Nerd Cat": {avatar_style: "cat", avatar_color: "#FFFFFF", avatar_accessory: "glasses", avatar_eyes: "wide", avatar_antenna: "none", avatar_cheeks: true, avatar_body_follow: false, avatar_body_color: "#4C6FFF"},
  "Alien Wink": {avatar_style: "round", avatar_color: "#9BE8A8", avatar_accessory: "bowtie", avatar_eyes: "wink", avatar_antenna: "double", avatar_cheeks: false, avatar_body_follow: false, avatar_body_color: "#7A4CD9"},
};
const pick = list => list[Math.floor(Math.random() * list.length)];
function hslToHex(h, s, l) {
  s /= 100; l /= 100;
  const k = n => (n + h / 30) % 12, a = s * Math.min(l, 1 - l);
  const f = n => Math.round(255 * (l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)))));
  return "#" + [f(0), f(8), f(4)].map(v => v.toString(16).padStart(2, "0")).join("");
}
function randomAvatar() {
  const hue = Math.floor(Math.random() * 360);
  return {
    avatar_style: pick(["round", "square", "cat", "bunny", "bear"]),
    avatar_eyes: pick(["round", "wide", "happy", "sleepy", "star", "wink"]),
    avatar_antenna: pick(["ball", "double", "bolt", "none"]),
    avatar_accessory: pick(["none", "glasses", "sunglasses", "headphones", "crown", "party", "cap", "bowtie"]),
    avatar_color: hslToHex(hue, 55 + Math.random() * 25, 78 + Math.random() * 12),
    avatar_position: pick(["auto", "alternate", "roam", "right", "left", "center", "mid_right", "mid_left"]),
    avatar_move: pick(["bounce", "walk_in", "pace", "float", "jump", "peek"]),
    avatar_body_follow: Math.random() < .4,
    avatar_body_color: hslToHex((hue + 150 + Math.random() * 60) % 360, 65 + Math.random() * 20, 52 + Math.random() * 10),
    avatar_cheeks: Math.random() < .5,
  };
}
function updateAvatarUi() {
  const preset = $("avatar-preset");
  if (preset && !preset.options.length) {
    preset.add(new Option("Choose a preset…", ""));
    Object.keys(AVATAR_PRESETS).forEach(name => preset.add(new Option(name, name)));
  }
  const custom = !!state.avatar_image;
  $("avatar-custom-preview").hidden = !custom;
  $("avatar-remove").hidden = !custom;
  if (custom) $("avatar-custom-preview").src = `/avatar/${state.avatar_image}.png`;
  $("avatar_body_color").disabled = state.avatar_body_follow;
  $("avatar-upload").textContent = custom ? "Replace image" : "Upload PNG / image";
}
function applyAvatar(values) {
  Object.assign(state, values, {avatar_image: ""});
  draw();
}

function updateVoices() {
  const select = $("voice");
  const choices = voiceChoices[state.tts] || [];
  const defaultLabel = state.tts === "kokoro" ? "Heart · American female (default)"
    : state.tts === "edge" ? "Brian · American male (default)" : "System default";
  select.replaceChildren(new Option(defaultLabel, ""));
  choices.forEach(voice => select.add(new Option(voice.name, voice.id)));
  if (!choices.some(voice => voice.id === state.voice)) state.voice = "";
  select.value = state.voice;
  select.disabled = state.tts === "silent";
  $("voice-hint").textContent = state.tts === "kokoro"
    ? kokoroReady ? "Natural speech, generated locally. Try Heart (American) or Emma (British)." : "Kokoro needs its local voice files and runtime. See README.md."
    : state.tts === "edge"
      ? edgeReady ? "Free Microsoft Edge neural voices (American, British, Australian, Filipino). Needs internet." : "Install edge-tts to enable Edge Neural voices."
      : state.tts === "silent" ? "Testing mode: the export will have no narration." : "Uses the voices installed in Windows.";
}

async function api(path, data) {
  const response = await fetch(path, data ? {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data)
  } : {});
  if (!response.ok) throw new Error((await response.json()).error || "Request failed.");
  return response;
}
function message(text, error = false) {
  $("job-status").textContent = text;
  $("job-status").classList.toggle("error", error);
}
function saveDraft() {
  try { localStorage.setItem("clipwright-project", JSON.stringify(state)); $("save-state").textContent = "Draft, autosaved"; }
  catch { $("save-state").textContent = "Use Save project to keep edits"; }
}
function changed() {
  saveDraft();
  document.documentElement.style.setProperty("--accent", state.accent);
  $("scene-count").textContent = `${state.scenes.length} scenes, about ${Math.round(state.scenes.reduce((n, s) => n + s.voiceover.trim().split(/\s+/).length * 60 / state.rate + .45, 0))} sec`;
  clearTimeout(timer);
  const version = ++previewVersion;
  timer = setTimeout(() => updatePreview(version), 250);
}
async function updatePreview(version) {
  try {
    const response = await api("/api/preview", { ...state, index: selected });
    const blob = await response.blob();
    if (version !== previewVersion) return;
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = URL.createObjectURL(blob);
    $("still").src = previewUrl;
  } catch (error) { if (version === previewVersion && !busy) message(error.message, true); }
}
function showStill() {
  $("video").pause(); $("video").hidden = true; $("still").hidden = false; $("back").hidden = true;
}
function drawScenes() {
  $("scenes").replaceChildren();
  state.scenes.forEach((scene, index) => {
    const card = document.createElement("article");
    card.className = `scene${index === selected ? " selected" : ""}`;
    const top = document.createElement("div"); top.className = "scene-top";
    const title = document.createElement("span"); title.textContent = `SCENE ${String(index + 1).padStart(2, "0")}`;
    const tools = document.createElement("div"); tools.className = "scene-tools";
    for (const [label, text, action, disabled] of [
      ["Move scene up", "↑", () => move(index, -1), index === 0],
      ["Move scene down", "↓", () => move(index, 1), index === state.scenes.length - 1],
      ["Delete scene", "×", () => { state.scenes.splice(index, 1); selected = Math.min(selected, state.scenes.length - 1); drawScenes(); changed(); }, state.scenes.length === 1]
    ]) {
      const button = document.createElement("button"); button.textContent = text; button.title = label;
      button.setAttribute("aria-label", `${label} ${index + 1}`); button.disabled = disabled;
      button.onclick = event => { event.stopPropagation(); action(); }; tools.append(button);
    }
    top.append(title, tools); card.append(top);
    for (const key of ["line1", "line2", "voiceover"]) {
      const input = document.createElement(key === "voiceover" ? "textarea" : "input");
      input.value = scene[key]; input.maxLength = key === "voiceover" ? 350 : 24;
      input.setAttribute("aria-label", `Scene ${index + 1} ${key === "voiceover" ? "voiceover" : key === "line1" ? "headline" : "accent headline"}`);
      if (key === "line2") input.className = "headline-accent";
      input.oninput = () => { scene[key] = key === "voiceover" ? input.value : input.value.toUpperCase(); changed(); };
      card.append(input);
    }
    const row = document.createElement("div"); row.className = "pose-row";
    const label = document.createElement("label"); label.textContent = "Mascot expression:"; label.htmlFor = `pose-${index}`;
    const pose = document.createElement("select"); pose.id = label.htmlFor;
    const poseLabels = {
      smile: "😊 Smile", happy: "😄 Happy", excited: "🤩 Excited", surprised: "😮 Surprised",
      shocked: "😱 Shocked", mindblown: "🤯 Mind blown", laugh: "😂 Laughing", wink: "😉 Winking",
      love: "😍 Heart-eyes", smirk: "😏 Smirk", thinking: "🤔 Thinking", confused: "😵 Confused",
      angry: "😠 Angry", sad: "😢 Sad", crying: "😭 Crying", flat: "😐 Deadpan",
    };
    for (const [val, text] of Object.entries(poseLabels)) pose.add(new Option(text, val));
    pose.value = scene.pose; pose.onchange = () => { scene.pose = pose.value; changed(); };
    row.append(label, pose); card.append(row);
    const query = document.createElement("input");
    query.className = "image-query"; query.maxLength = 160;
    query.placeholder = "Image keywords, e.g. laptop computer";
    query.value = scene.image_query || "";
    query.setAttribute("aria-label", `Scene ${index + 1} image search keywords`);
    query.oninput = () => { scene.image_query = query.value; saveDraft(); };
    const imageTools = document.createElement("div"); imageTools.className = "image-tools";
    const find = document.createElement("button"); find.textContent = scene.image ? "Replace image" : "Find image";
    find.onclick = event => { event.stopPropagation(); run("images", index); };
    const upload = document.createElement("button"); upload.textContent = "Upload";
    upload.onclick = event => {
      event.stopPropagation();
      const picker = document.createElement("input"); picker.type = "file"; picker.accept = "image/*";
      picker.onchange = async () => {
        const file = picker.files[0]; if (!file) return;
        try {
          const response = await fetch("/api/upload-image", {
            method: "POST",
            headers: { "Content-Type": file.type || "application/octet-stream", "X-Filename": encodeURIComponent(file.name) },
            body: await file.arrayBuffer(),
          });
          if (!response.ok) throw new Error((await response.json()).error || "Upload failed.");
          scene.image = (await response.json()).id;
          drawScenes(); changed(); message(`Uploaded image for scene ${index + 1}.`);
        } catch (error) { message(error.message, true); }
      };
      picker.click();
    };
    imageTools.append(find, upload);
    if (scene.image) {
      const thumb = document.createElement("img"); thumb.src = `/media/${scene.image}.jpg`; thumb.alt = "Scene image";
      const source = document.createElement("a"); source.textContent = "Source & license";
      source.href = `/media/${scene.image}.json`; source.target = "_blank"; source.rel = "noopener";
      fetch(source.href).then(response => response.json()).then(info => {
        if (typeof info.source === "string" && info.source.startsWith("https://")) source.href = info.source;
        else if (info.source === "local-upload") { source.textContent = "Local upload"; source.removeAttribute("href"); }
        source.title = `${info.author || ""} · ${info.license || ""}`;
      }).catch(() => { });
      const remove = document.createElement("button"); remove.textContent = "Remove";
      remove.onclick = event => { event.stopPropagation(); delete scene.image; drawScenes(); changed(); };
      imageTools.append(thumb, source, remove);
    }
    card.append(query, imageTools);
    const select = () => {
      if (selected === index) return;
      selected = index;
      document.querySelectorAll(".scene").forEach((node, i) => node.classList.toggle("selected", i === selected));
      showStill(); changed();
    };
    card.onclick = select; card.onfocusin = select;
    $("scenes").append(card);
  });
  $("add").disabled = state.scenes.length >= 12;
}
function move(index, direction) {
  const target = index + direction;
  [state.scenes[index], state.scenes[target]] = [state.scenes[target], state.scenes[index]];
  selected = target; drawScenes(); changed();
}
function draw() {
  fields.forEach(key => { if (flags.has(key)) $(key).checked = state[key]; else $(key).value = state[key]; });
  updateVoices();
  updateModelChoices();
  updateMusicChoices();
  updateAvatarUi();
  document.querySelectorAll("[data-tone]").forEach(button => {
    const active = button.dataset.tone === state.tone;
    button.classList.toggle("selected", active); button.setAttribute("aria-pressed", active);
  });
  drawScenes(); changed();
}
function renderChat() {
  const log = $("chat-log");
  log.replaceChildren();
  log.hidden = chatHistory.length === 0;
  for (const item of chatHistory) {
    const div = document.createElement("div");
    div.className = `chat-msg ${item.role}`;
    div.textContent = item.text;
    log.append(div);
  }
  log.scrollTop = log.scrollHeight;
  $("undo-edit").disabled = undoStack.length === 0 || busy;
}
async function run(action, imageTarget = null, instruction = "") {
  if (busy) return;
  if (action === "revise" && !instruction.trim()) {
    message("Type an edit instruction first, e.g. 'make it 30 seconds'.", true);
    $("chat-input").focus();
    return;
  }
  busy = true;
  jobButtons.forEach(id => $(id).disabled = true);
  $("undo-edit").disabled = true;
  $("task-progress").hidden = false;
  $("task-dismiss").hidden = true;
  $("token-live").hidden = action !== "generate" && action !== "revise";
  $("token-live").textContent = "🔥 0 tokens";
  $("task-title").textContent = {
    generate: "🔥 Letting him cook…", images: "Finding scene images",
    revise: "🔥 Cooking script edit…", download_model: "Downloading local AI model", motion: "Rendering scene animation", audio: "Preparing voice preview", render: "Creating your video"
  }[action];
  $("task-stage").textContent = "Starting…";
  $("progress").hidden = false;
  $("progress").removeAttribute("value");
  const started = Date.now();
  const updateElapsed = () => {
    const seconds = Math.floor((Date.now() - started) / 1000);
    $("task-elapsed").textContent = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")} elapsed`;
  };
  updateElapsed();
  const clock = setInterval(updateElapsed, 1000);
  message("Starting…");
  if (action === "render") $("download").hidden = true;
  const payload = structuredClone(state);
  const snapshot = JSON.stringify(state);
  if (action === "audio" || action === "motion") {
    payload.scenes = [payload.scenes[selected]];
    payload.scene_offset = selected;
  }
  if (action === "images" && imageTarget !== null) payload.image_target = imageTarget;
  if (action === "download_model") payload.download_model_key = $("download-model-key").value;
  if (action === "revise") {
    payload.instruction = instruction.trim();
    payload.revise_scope = $("revise-scope").value;
    payload.selected_index = selected;
    payload.chat_history = chatHistory.slice(-10);
  }
  try {
    const { id } = await (await api("/api/jobs", { ...payload, action })).json();
    let job;
    do {
      await new Promise(resolve => setTimeout(resolve, action === "generate" || action === "revise" ? 320 : 800));
      job = await (await api(`/api/jobs/${id}`)).json();
      message(job.message);
      const tokMatch = /(\d+) gen \+ (\d+) prompt = (\d+) tokens(?: \(([\d.]+ tok\/s)\))?/.exec(job.message || "");
      if (tokMatch) {
        const rateText = tokMatch[4] ? ` · ${tokMatch[4]}` : "";
        $("token-live").hidden = false;
        $("token-live").textContent = `🔥 ${tokMatch[3]} tokens (${tokMatch[1]} gen + ${tokMatch[2]} prompt${rateText})`;
      }
      const frame = /^frame (\d+)\/(\d+)$/.exec(job.message);
      if (frame && Number(frame[2]) > 0) {
        const percent = Math.min(99, Math.floor(Number(frame[1]) / Number(frame[2]) * 100));
        $("progress").value = percent;
        $("task-stage").textContent = `Rendering frames · ${percent}%`;
      } else {
        $("task-stage").textContent = job.message;
      }
    } while (job.status === "running");
    if (job.status === "error") throw new Error(job.message);
    $("progress").value = 100;
    $("task-title").textContent = "Complete";
    $("task-stage").textContent = {
      generate: "Your script is ready to review.", images: "Image search finished.",
      revise: job.script?.summary || "Script updated.", download_model: "Model downloaded and selected.", motion: "Your scene animation is ready.", audio: "Your voice preview is ready.", render: "Your MP4 is ready to download."
    }[action];
    if (action === "download_model") {
      installedModels = job.models || installedModels;
      modelCatalog = job.model_catalog || modelCatalog;
      if (job.model) state.model = job.model;
      draw();
      message("Model downloaded and selected in Voice & model settings.");
      return;
    }
    if (action === "generate" || action === "images" || action === "revise") {
      if (JSON.stringify(state) !== snapshot && !confirm("You edited the project while this job ran. Apply its scene results and replace those edits?")) {
        message("Kept your current edits."); return;
      }
      if (action === "revise") {
        undoStack.push(structuredClone(state.scenes));
        if (undoStack.length > 15) undoStack.shift();
        chatHistory.push({ role: "user", text: instruction.trim() });
        chatHistory.push({ role: "assistant", text: job.script.summary || "Updated your script." });
        $("chat-input").value = "";
        renderChat();
      }
      state.scenes = job.script.scenes;
      if (action === "generate") {
        selected = 0;
        if (job.script.direction && typeof job.script.direction === "object") {
          const { vibe, vibe_label, ...styleProps } = job.script.direction;
          Object.assign(state, styleProps);
        }
      } else {
        selected = Math.min(selected, state.scenes.length - 1);
      }
      const stats = job.script.token_stats;
      const dir = job.script.direction;
      if (stats) {
        const tokText = `🔥 ${stats.total_tokens} tokens burned (${stats.output_tokens} gen + ${stats.prompt_tokens} prompt · ${stats.tok_per_sec} tok/s)`;
        $("token-live").hidden = false;
        $("token-live").textContent = tokText;
        const summaryBox = $("cook-summary");
        if (summaryBox) {
          const vibeInfo = dir ? ` · Auto-styled for ${dir.vibe_label} (${dir.theme} theme, ${dir.font_style} font, ${dir.bgm})` : "";
          summaryBox.textContent = `${tokText}${vibeInfo}`;
          summaryBox.hidden = false;
        }
      }
      if (Array.isArray(job.script.sources) && job.script.sources.length) {
        const box = $("web-sources");
        box.replaceChildren("Sources used: ");
        job.script.sources.slice(0, 4).forEach((s, i) => {
          if (i) box.append(" · ");
          if (typeof s.url === "string" && s.url.startsWith("https://")) {
            const a = document.createElement("a"); a.href = s.url; a.target = "_blank"; a.rel = "noopener";
            a.textContent = (s.title || "Source").slice(0, 32); box.append(a);
          }
        });
        box.hidden = false;
      }
      draw(); showStill();
      const notes = job.script.media_notes || [];
      const okMsg = action === "images" ? "Scene images are ready."
        : action === "revise" ? (job.script.summary || "Script updated. Use Undo to revert.")
          : "Script ready. Review and edit each scene.";
      message(notes.length ? notes.join(" ") : okMsg, notes.length > 0);
      if (notes.length) $("task-stage").textContent = notes.join(" ");
    } else if (action === "audio") {
      $("audio").src = job.url; $("audio").hidden = false;
      $("audio").play().catch(() => message("Voiceover ready. Press play below the preview."));
    } else {
      $("video").src = job.url; $("video").hidden = false; $("still").hidden = true;
      $("back").hidden = false;
      if (action === "render") {
        $("download").href = job.url; $("download").hidden = false;
        $("credits").href = job.credits; $("credits").hidden = false;
        message("Your video is ready. Play it above or download the MP4.");
      } else {
        message("Animated scene preview ready (540 × 960). Export renders at full resolution.");
        $("video").play().catch(() => { });
      }
    }
  } catch (error) {
    message(error.message, true);
    $("task-title").textContent = "Could not finish";
    $("task-stage").textContent = error.message;
    $("progress").hidden = true;
  }
  finally {
    clearInterval(clock);
    updateElapsed();
    busy = false;
    $("task-dismiss").hidden = false;
    jobButtons.forEach(id => $(id).disabled = false);
    $("undo-edit").disabled = undoStack.length === 0;
  }
}
async function start() {
  const initial = await (await api("/api/init")).json();
  kokoroReady = initial.kokoro_ready;
  edgeReady = initial.edge_ready;
  installedModels = initial.models || [];
  modelCatalog = initial.model_catalog || [];
  musicTracks = initial.music_tracks || [];
  voiceChoices = {
    kokoro: initial.kokoro_voices,
    edge: initial.edge_voices || [],
    pyttsx3: initial.voices.map(name => ({ id: name, name })),
  };
  const defaults = {
    ...initial.script, tone: "Hyped", tts: kokoroReady ? "kokoro" : edgeReady ? "edge" : "pyttsx3", voice: "", rate: 185,
    model: initial.models[0] || "", gpu_layers: 35, n_ctx: 4096, accent: "#FF6B3D", fps: 30,
    theme: "dark", font_style: "impact", bg_effect: "orbs", text_anim: "slide", caption_style: "box", caption_anim: "highlight", transition: "fade", camera_style: "ken_burns",
    motion: "lively", talking: true, avatar_style: "round", avatar_color: "#F4F1EA",
    avatar_accessory: "none", avatar_size: 100, avatar_eyes: "round", avatar_antenna: "ball", avatar_position: "auto", avatar_move: "bounce",
    avatar_body_color: "#FF6B3D", avatar_cheeks: false, avatar_body_follow: true, avatar_image: "",
    bgm: "synth_lofi", bgm_volume: 18, target_scenes: 6, render_quality: "hd",
    auto_images: true, web_search: true
  };
  state = structuredClone(defaults);
  try {
    const saved = JSON.parse(localStorage.getItem("clipwright-project"));
    if (saved) {
      if (saved.gpu_layers === 20) saved.gpu_layers = 35;
      await api("/api/preview", saved);
      state = { ...defaults, ...saved };
    }
  } catch { message("Loaded the sample project."); }
  if (!state.model && defaults.model) {
    state.model = defaults.model;
    state.gpu_layers = defaults.gpu_layers;
  }
  $("model-hint").textContent = initial.models.length ? "Local model found. Ready to write." : "Start with the sample, or choose a GGUF model in settings to generate your own script.";
  fields.forEach(key => $(key).addEventListener("input", () => {
    state[key] = flags.has(key) ? $(key).checked : numeric.has(key) ? Number($(key).value) : $(key).value;
    if (key === "tts") { state.voice = ""; updateVoices(); }
    changed();
  }));
  document.querySelectorAll("[data-tone]").forEach(button => button.onclick = () => {
    state.tone = button.dataset.tone; state.rate = rates[state.tone]; draw();
  });
  $("add").onclick = () => {
    state.scenes.push({ line1: "YOUR NEXT", line2: "BIG IDEA", voiceover: "Write your voiceover here.", pose: "smile" });
    selected = state.scenes.length - 1; drawScenes(); changed();
  };
  $("generate").onclick = () => run("generate");
  $("render").onclick = () => run("render");
  $("play").onclick = () => run("audio");
  $("motion-preview").onclick = () => run("motion");
  $("collect-images").onclick = () => run("images");
  $("look-random").onclick = () => {
    const options = id => [...$(id).options].map(o => o.value);
    const accent = hslToHex(Math.floor(Math.random() * 360), 70 + Math.random() * 20, 52 + Math.random() * 8);
    Object.assign(state, {
      theme: pick(options("theme")), font_style: pick(options("font_style")), bg_effect: pick(options("bg_effect")),
      text_anim: pick(options("text_anim")), caption_style: pick(options("caption_style")),
      caption_anim: pick(options("caption_anim")), transition: pick(options("transition")),
      camera_style: pick(options("camera_style").filter(v => v !== "static")),
      motion: pick(options("motion").filter(v => v !== "none")), accent,
    });
    draw();
    message("Randomized theme and effects. Click again for another look.");
  };
  $("avatar-preset").onchange = () => {
    const preset = AVATAR_PRESETS[$("avatar-preset").value];
    if (preset) applyAvatar(preset);
  };
  $("avatar-random").onclick = () => { applyAvatar(randomAvatar()); $("avatar-preset").value = ""; };
  $("avatar_body_follow").addEventListener("input", updateAvatarUi);
  $("avatar-remove").onclick = () => { state.avatar_image = ""; draw(); message("Back to the drawn character."); };
  $("avatar-upload").onclick = () => {
    const picker = document.createElement("input"); picker.type = "file"; picker.accept = "image/*";
    picker.onchange = async () => {
      const file = picker.files[0]; if (!file) return;
      try {
        const response = await fetch("/api/upload-avatar", {method: "POST", headers: {"Content-Type": file.type || "application/octet-stream"}, body: await file.arrayBuffer()});
        if (!response.ok) throw new Error((await response.json()).error || "Upload failed.");
        state.avatar_image = (await response.json()).id;
        draw(); message("Custom avatar added. It replaces the drawn character.");
      } catch (error) { message(error.message, true); }
    };
    picker.click();
  };
  $("download-model-btn").onclick = () => run("download_model");
  $("bgm-random").onclick = () => {
    if (!musicTracks.length) return;
    state.bgm = pick(musicTracks).id;
    draw();
    message(`Selected background music: ${$("bgm").options[$("bgm").selectedIndex]?.text || state.bgm}`);
  };
  $("bgm-preview").onclick = () => {
    if (!state.bgm || state.bgm === "none") {
      message("Choose a background music track first.", true);
      return;
    }
    const player = $("bgm-player");
    player.src = `/music/${state.bgm}.wav`;
    player.volume = Math.min(1, Math.max(0.1, (state.bgm_volume || 18) / 50));
    player.hidden = false;
    message("Loading music preview…");
    player.play().then(() => message("Playing background music preview.")).catch(() => message("Press play on the audio control below."));
  };
  $("bgm-upload").onclick = () => {
    const picker = document.createElement("input"); picker.type = "file"; picker.accept = "audio/*,.mp3,.wav,.ogg,.m4a,.flac";
    picker.onchange = async () => {
      const file = picker.files[0]; if (!file) return;
      try {
        message("Uploading background music…");
        const response = await fetch("/api/upload-music", {
          method: "POST",
          headers: { "Content-Type": file.type || "application/octet-stream", "X-Filename": encodeURIComponent(file.name) },
          body: await file.arrayBuffer(),
        });
        if (!response.ok) throw new Error((await response.json()).error || "Music upload failed.");
        const track = await response.json();
        musicTracks = [track, ...musicTracks.filter(t => t.id !== track.id)];
        state.bgm = track.id;
        draw();
        message(`Added background music: ${track.name}`);
      } catch (error) { message(error.message, true); }
    };
    picker.click();
  };
  $("bgm-search").onclick = async () => {
    const q = $("bgm-query").value.trim();
    if (!q) { message("Enter music search keywords first, e.g. 'lofi' or 'ambient'.", true); return; }
    try {
      $("bgm-search").disabled = true;
      message(`Searching open-source music for "${q}"…`);
      const response = await api("/api/search-music", { query: q });
      const track = await response.json();
      musicTracks = [track, ...musicTracks.filter(t => t.id !== track.id)];
      state.bgm = track.id;
      draw();
      message(`Found and selected: ${track.name}`);
    } catch (error) { message(error.message, true); }
    finally { $("bgm-search").disabled = false; }
  };
  $("model-select").onchange = () => {
    const val = $("model-select").value;
    if (val && val !== "__custom__") {
      state.model = val;
      $("model").value = val;
      changed();
    } else {
      $("model").focus();
    }
  };
  $("revise-btn").onclick = () => run("revise", null, $("chat-input").value);
  $("chat-input").addEventListener("keydown", event => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      run("revise", null, $("chat-input").value);
    }
  });
  document.querySelectorAll(".chip[data-prompt]").forEach(chip => chip.onclick = () => {
    $("chat-input").value = chip.dataset.prompt;
    run("revise", null, chip.dataset.prompt);
  });
  $("undo-edit").onclick = () => {
    if (!undoStack.length || busy) return;
    state.scenes = undoStack.pop();
    selected = Math.min(selected, state.scenes.length - 1);
    renderChat(); draw(); showStill();
    message("Reverted last AI script edit.");
  };
  $("back").onclick = showStill;
  $("task-dismiss").onclick = () => $("task-progress").hidden = true;
  $("save").onclick = () => {
    const url = URL.createObjectURL(new Blob([JSON.stringify(state, null, 2)], { type: "application/json" }));
    const link = document.createElement("a"); link.href = url; link.download = "clipwright-project.json"; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  $("load").onclick = () => $("project-file").click();
  $("project-file").onchange = async event => {
    try {
      const file = event.target.files[0]; if (!file) return;
      const next = { ...defaults, ...JSON.parse(await file.text()) };
      await api("/api/preview", next);
      state = next; selected = 0; draw(); showStill(); message("Project opened.");
    } catch (error) { message(`Could not open project: ${error.message}`, true); }
    finally { event.target.value = ""; }
  };
  draw();
}
start().catch(error => message(`Could not start studio: ${error.message}`, true));
