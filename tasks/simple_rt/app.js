(() => {
  const API = "";
  const PRACTICE = 2;

  const el = {
    start: document.getElementById("panel-start"),
    task: document.getElementById("panel-task"),
    done: document.getElementById("panel-done"),
    stage: document.getElementById("stage"),
    progress: document.getElementById("progress"),
    hint: document.getElementById("hint"),
    summaryBox: document.getElementById("summaryBox"),
    exportLink: document.getElementById("exportLink"),
    nTrials: document.getElementById("nTrials"),
    btnStart: document.getElementById("btnStart"),
    btnAgain: document.getElementById("btnAgain"),
  };

  let sessionId = null;
  let listening = false;
  let onset = 0;
  let foreperiodTimer = null;
  let resolveTrial = null;

  function deviceInfo() {
    return JSON.stringify({
      userAgent: navigator.userAgent,
      language: navigator.language,
      screen: `${window.screen.width}x${window.screen.height}`,
      touch: "ontouchstart" in window,
    });
  }

  async function api(path, opts = {}) {
    const res = await fetch(`${API}${path}`, {
      headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
      ...opts,
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`${res.status} ${text}`);
    }
    if (res.status === 204) return null;
    const ct = res.headers.get("content-type") || "";
    if (ct.includes("application/json")) return res.json();
    return res.text();
  }

  function sleep(ms) {
    return new Promise((r) => setTimeout(r, ms));
  }

  function randomForeperiod() {
    // Rough exponential-style delay between 700–1500 ms
    return 700 + Math.floor(Math.random() * 800);
  }

  function onResponse(kind) {
    if (!listening || !resolveTrial) return;
    const rt = performance.now() - onset;
    listening = false;
    const fn = resolveTrial;
    resolveTrial = null;
    fn({ response: kind, rt_ms: Math.round(rt * 10) / 10 });
  }

  window.addEventListener("keydown", (e) => {
    if (e.code === "Space") {
      e.preventDefault();
      onResponse("space");
    }
  });
  el.stage.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    onResponse("pointer");
  });

  async function runOneTrial(trialIndex, trialType) {
    el.progress.textContent = `${trialType} trial ${trialIndex + 1}`;
    el.hint.textContent = "Wait for green…";
    el.stage.className = "stage wait";
    el.stage.textContent = "WAIT";

    await sleep(randomForeperiod());

    el.stage.className = "stage go";
    el.stage.textContent = "GO!";
    el.hint.textContent = "Respond now (Space or tap)";
    onset = performance.now();
    listening = true;

    const result = await new Promise((resolve) => {
      resolveTrial = resolve;
    });

    el.stage.className = "stage blank";
    el.stage.textContent = "…";
    await sleep(400);

    return {
      trial_index: trialIndex,
      trial_type: trialType,
      stimulus_id: "go",
      response: result.response,
      correct: true,
      rt_ms: result.rt_ms,
      client_ts: new Date().toISOString(),
    };
  }

  async function runSession() {
    const nTest = Number(el.nTrials.value) || 10;
    el.start.classList.add("hidden");
    el.done.classList.add("hidden");
    el.task.classList.remove("hidden");

    const session = await api("/v1/sessions", {
      method: "POST",
      body: JSON.stringify({
        task_id: "simple_rt",
        device_info: deviceInfo(),
        n_trials: nTest,
      }),
    });
    sessionId = session.id;

    let idx = 0;
    async function collectAndPost(trialType) {
      const trial = await runOneTrial(idx++, trialType);
      // Persist each trial
      await api(`/v1/sessions/${sessionId}/trials`, {
        method: "POST",
        body: JSON.stringify({ trials: [trial] }),
      });
    }
    for (let i = 0; i < PRACTICE; i++) {
      await collectAndPost("practice");
    }
    for (let i = 0; i < nTest; i++) {
      await collectAndPost("test");
    }

    const completed = await api(`/v1/sessions/${sessionId}/complete`, { method: "POST" });
    el.task.classList.add("hidden");
    el.done.classList.remove("hidden");
    el.summaryBox.textContent = JSON.stringify(completed.summary, null, 2);
    el.exportLink.href = `/v1/sessions/${sessionId}/export.csv`;
  }

  el.btnStart.addEventListener("click", () => {
    runSession().catch((err) => {
      alert(err.message);
      console.error(err);
    });
  });
  el.btnAgain.addEventListener("click", () => {
    el.done.classList.add("hidden");
    el.start.classList.remove("hidden");
  });
})();
