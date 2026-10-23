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
    statusText.textContent = "กำลังตรวจสอบใบเสร็จ…";

    try {
        const response = await fetch("/api/extract", {
            method: "POST",
            body: formData,
        });

        const data = await response.json();

        if (!response.ok) {
            const message =
                typeof data.detail === "string"
                    ? data.detail
                    : `ข้อมูลไม่ผ่านการตรวจสอบ: HTTP ${response.status}`;

            throw new Error(message);
        }

        const labels = {
            receipt: "AI จัดประเภทว่าเป็นใบเสร็จร้านค้า",
            not_receipt: "AI จัดประเภทว่าไม่ใช่ใบเสร็จร้านค้า",
            unclear: "ยังระบุไม่ได้ กรุณาส่งข้อมูลหรือภาพที่ชัดขึ้น",
        };

        statusText.textContent = labels[data.document_type];
        resultBox.textContent = JSON.stringify(data, null, 2);
        copyButton.disabled = false;

    } catch (error) {
        statusText.textContent = `ไม่สำเร็จ: ${error.message}`;
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