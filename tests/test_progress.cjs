const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

async function check() {
  const elements = new Map(), values = [];
  let clocks = 0;
  const document = {getElementById(id) {
    if (!elements.has(id)) elements.set(id, {
      hidden: false, disabled: false, textContent: "",
      classList: {toggle() {}},
      removeAttribute() {},
    });
    return elements.get(id);
  }};
  const context = vm.createContext({
    document, structuredClone, console,
    setTimeout: callback => {callback();},
    setInterval: () => {clocks++; return 1;},
    clearInterval: () => {clocks--;},
  });
  const source = fs.readFileSync("web/studio.js", "utf8").replace(/^start\(\)\.catch.*$/m, "");
  vm.runInContext(source, context);
  Object.defineProperty(document.getElementById("progress"), "value", {
    configurable: true,
    set(value) {values.push(value);},
  });
  await vm.runInContext(`
    state = {scenes: [{voiceover: "Hello"}]};
    var responses = [
      {id: "render-test"},
      {status: "running", message: "frame 50/100"},
      {status: "done", message: "Ready", url: "/video.mp4"}
    ];
    api = async () => ({json: async () => responses.shift()});
    run("render");
  `, context);
  assert.deepEqual(values, [50, 100]);
  assert.equal(elements.get("task-title").textContent, "Complete");
  assert.equal(elements.get("task-dismiss").hidden, false);
  assert.equal(elements.get("render").disabled, false);
  assert.equal(clocks, 0);
  await vm.runInContext(`
    responses = [{id: "failed-test"}, {status: "error", message: "Voice unavailable"}];
    run("audio");
  `, context);
  assert.equal(elements.get("progress").hidden, true);
  assert.equal(elements.get("task-stage").textContent, "Voice unavailable");
  assert.equal(elements.get("play").disabled, false);
  assert.equal(clocks, 0);
  assert.equal(vm.runInContext("busy", context), false);
  console.log("Progress success, failure, and timer cleanup passed.");
}
check().catch(error => {console.error(error); process.exitCode = 1;});
