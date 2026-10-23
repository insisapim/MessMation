const modeInput = document.querySelector("#mode");
const sourceInput = document.querySelector("#source");
const imageInput = document.querySelector("#image");

const textPanel = document.querySelector("#text-panel");
const imagePanel = document.querySelector("#image-panel");
const preview = document.querySelector("#preview");

const extractButton = document.querySelector("#extract");
const copyButton = document.querySelector("#copy");

const statusText = document.querySelector("#status");
const resultBox = document.querySelector("#result");

const processLog = document.querySelector("#process-log");
const runMode = document.querySelector("#run-mode");

let previewUrl = null;

function resetResult() {
    statusText.textContent = "รอข้อมูลต้นฉบับ";
    resultBox.textContent = "";
    copyButton.disabled = true;
}

modeInput.addEventListener("change", () => {
    const isImage = modeInput.value === "image";

    textPanel.hidden = isImage;
    imagePanel.hidden = !isImage;

    resetResult();
});

sourceInput.addEventListener("input", resetResult);

imageInput.addEventListener("change", () => {
    resetResult();

    if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
        previewUrl = null;
    }

    preview.hidden = true;
    preview.removeAttribute("src");

    const file = imageInput.files[0];

    if (!file) return;

    if (file.size > 5 * 1024 * 1024) {
        statusText.textContent = "ภาพต้องมีขนาดไม่เกิน 5 MiB";
        imageInput.value = "";
        return;
    }

    previewUrl = URL.createObjectURL(file);
    preview.src = previewUrl;
    preview.hidden = false;
});

preview.addEventListener("error", () => {
    preview.hidden = true;
    imageInput.value = "";
    statusText.textContent = "ไม่สามารถแสดงไฟล์นี้เป็นรูปภาพได้";

    if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
        previewUrl = null;
    }
});

extractButton.addEventListener("click", async () => {
    resetResult();

    processLog.replaceChildren();
    runMode.textContent = "";

    const formData = new FormData();
    formData.append("mode", modeInput.value);

    if (modeInput.value === "text") {
        const text = sourceInput.value.trim();

        if (!text) {
            statusText.textContent = "กรุณากรอกข้อความ";
            return;
        }

        formData.append("text", text);
    } else {
        const file = imageInput.files[0];

        if (!file) {
            statusText.textContent = "กรุณาเลือกรูปภาพ";
            return;
        }

        formData.append("image", file);
    }

    const controls = [
        extractButton,
        modeInput,
        sourceInput,
        imageInput,
    ];

    controls.forEach(element => element.disabled = true);
    copyButton.disabled = true;

    statusText.textContent = "กำลังส่งข้อมูล…";
    addLog("กำลังส่งข้อมูลไป Backend");

    try {
        const response = await fetch("/api/extract/stream", {
            method: "POST",
            body: formData,
        });

        if (!response.ok) {
            const body = await response.json();

            throw new Error(
                typeof body.detail === "string"
                    ? body.detail
                    : `คำขอไม่สำเร็จ: HTTP ${response.status}`
            );
        }

        const contentType = response.headers.get("content-type") || "";

        if (!contentType.includes("text/event-stream")) {
            throw new Error("Backend ไม่ได้ส่งข้อมูลแบบ SSE");
        }

        await readSSE(response, event => {
            const prefix = event.demo ? "[จำลอง] " : "";

            if (event.demo) {
                runMode.textContent =
                    "โหมดจำลอง: ไม่ได้เรียก AI ผลลัพธ์ไม่ใช่ข้อมูลจากเอกสาร";
            }

            if (event.type === "progress") {
                addLog(prefix + event.message);
                statusText.textContent = prefix + event.message;
            }

            else if (event.type === "result") {
                const result = event.data;

                if (
                    result.document_type === "receipt"
                    && result.data !== null
                ) {
                    resultBox.textContent =
                        JSON.stringify(result.data, null, 2);

                    statusText.textContent = event.demo
                        ? "แสดงผลจำลองแล้ว"
                        : "ข้อมูลผ่าน schema แล้ว กรุณาตรวจเทียบกับต้นฉบับ";

                    copyButton.disabled = event.demo;
                } else {
                    resultBox.textContent = "";
                    copyButton.disabled = true;

                    statusText.textContent =
                        prefix + result.reason;
                }

                addLog(prefix + "ได้รับผลลัพธ์แล้ว");
            }

            else if (event.type === "error") {
                addLog(prefix + event.message, "error");

                statusText.textContent =
                    "ไม่สำเร็จ: " + event.message;

                resultBox.textContent = "";
                copyButton.disabled = true;
            }

            else if (event.type === "done") {
                addLog(prefix + "จบการทำงาน");
            }
        });

    } catch (error) {
        addLog(error.message, "error");

        statusText.textContent =
            `เกิดข้อผิดพลาด: ${error.message}`;

        resultBox.textContent = "";
        copyButton.disabled = true;
    } finally {
        controls.forEach(element => element.disabled = false);
    }
});

copyButton.addEventListener("click", async () => {
    try {
        await navigator.clipboard.writeText(resultBox.textContent);
        statusText.textContent = "คัดลอก JSON แล้ว";
    } catch {
        statusText.textContent = "กรุณาเลือกข้อความแล้วคัดลอกด้วยตนเอง";
    }
});

function addLog(message, level = "info") {
    const item = document.createElement("li");
    const time = new Date().toLocaleTimeString("th-TH");

    item.textContent = `[${time}] ${message}`;
    item.dataset.level = level;

    processLog.appendChild(item);
    processLog.scrollTop = processLog.scrollHeight;
}

async function readSSE(response, onEvent) {
    if (!response.body) {
        throw new Error("ไม่พบข้อมูล stream");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    let buffer = "";
    let completed = false;
    let receivedOutcome = false;

    function consumeFrames() {
        while (true) {
            const separator = /\r?\n\r?\n/.exec(buffer);

            if (!separator) break;

            const frame = buffer.slice(0, separator.index);

            buffer = buffer.slice(
                separator.index + separator[0].length
            );

            const data = frame
                .split(/\r?\n/)
                .filter(line => line.startsWith("data:"))
                .map(line => line.slice(5).trimStart())
                .join("\n");

            if (!data) continue;

            const event = JSON.parse(data);

            if (event.type === "result" || event.type === "error") {
                receivedOutcome = true;
            }

            if (event.type === "done") {
                completed = true;
            }

            onEvent(event);
        }
    }

    try {
        while (true) {
            const { value, done } = await reader.read();

            if (done) {
                buffer += decoder.decode();
                consumeFrames();
                break;
            }

            buffer += decoder.decode(value, { stream: true });
            consumeFrames();
        }

        if (!completed || !receivedOutcome || buffer.trim()) {
            throw new Error("การเชื่อมต่อจบก่อนรับข้อมูลครบ");
        }
    } finally {
        try {
            await reader.cancel();
        } finally {
            reader.releaseLock();
        }
    }
}