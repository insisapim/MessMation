"use strict";
const $ = selector => document.querySelector(selector);
const sourceInput = $("#source");
const imageInput = $("#image");
const preview = $("#preview");
const tabs = [...document.querySelectorAll("[data-mode]")];
const resultBox = $("#result");
const processLog = $("#process-log");
let mode = "text";
let busy = false;
let previewUrl = null;
let controller = null;
let receiptData = null;
let demoResult = false;

function setStatus(message, state = "idle") {
    $("#status").textContent = message;
    const labels = {idle: "รอข้อมูล", busy: "กำลังทำงาน", success: "ผ่านรูปแบบ", error: "ไม่สำเร็จ", rejected: "ตรวจเอกสารแล้ว"};
    $("#state-badge").textContent = labels[state];
    $("#state-badge").dataset.state = state;
}
function clearOutput() {
    receiptData = null;
    demoResult = false;
    resultBox.textContent = "";
    $("#receipt-summary").hidden = true;
    $("#empty-state").hidden = false;
    $("#empty-title").textContent = "เริ่มจากใบเสร็จของคุณ";
    $("#empty-description").textContent = "ข้อมูล 5 ช่อง จัดเป็นระเบียบ พร้อมนำไปใช้ต่อในรูปแบบ JSON";
    $("#copy").disabled = true;
    $("#download").disabled = true;
    $("#run-mode").hidden = true;
    $("#run-mode").textContent = "";
    $(".json-details").open = false;
}
function resetResult() {
    clearOutput();
    setStatus("ผลลัพธ์จะอยู่ตรงนี้ หลังจากแปลงข้อมูล");
    processLog.replaceChildren();
    $("#log-empty").hidden = false;
    $("#log-count").textContent = "ยังไม่มีรายการ";
}
function updateCount() {
    $("#char-count").textContent = `${sourceInput.value.length.toLocaleString("en-US")} / 12,000`;
}
function selectMode(value) {
    if (busy) return;
    mode = value;
    tabs.forEach(tab => {
        const selected = tab.dataset.mode === mode;
        tab.setAttribute("aria-selected", String(selected));
        tab.tabIndex = selected ? 0 : -1;
    });
    $("#text-panel").hidden = mode !== "text";
    $("#image-panel").hidden = mode !== "image";
    resetResult();
}
tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => selectMode(tab.dataset.mode));
    tab.addEventListener("keydown", event => {
        let next;
        if (["ArrowLeft", "ArrowRight"].includes(event.key)) next = 1 - index;
        else if (event.key === "Home") next = 0;
        else if (event.key === "End") next = 1;
        else return;
        event.preventDefault();
        selectMode(tabs[next].dataset.mode);
        tabs[next].focus();
    });
});
sourceInput.addEventListener("input", () => {resetResult(); updateCount();});
$("#sample").addEventListener("click", () => {
    sourceInput.value = "ร้านกาแฟมุมตึก\nใบเสร็จรับเงินเลขที่ MM-001\nวันที่ 2026-10-24\nอเมริกาโน 60 บาท\nครัวซองต์ 75 บาท\nยอดสุทธิ 135 บาท\nรับเงินสด 200 บาท\nเงินทอน 65 บาท";
    updateCount(); resetResult(); sourceInput.focus();
});
function clearPreview() {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = null;
    preview.hidden = true;
    preview.removeAttribute("src");
    $("#upload-prompt").hidden = false;
    $("#file-info").textContent = "เลือกภาพที่เห็นชื่อร้าน วันที่ และยอดรวมชัดเจน";
}
function loadImage() {
    resetResult(); clearPreview();
    const file = imageInput.files[0];
    if (!file) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
        imageInput.value = "";
        setStatus("รองรับเฉพาะภาพ JPG, PNG และ WebP", "error"); return;
    }
    if (file.size > 5 * 1024 * 1024) {
        imageInput.value = "";
        setStatus("ภาพต้องมีขนาดไม่เกิน 5 MiB", "error"); return;
    }
    previewUrl = URL.createObjectURL(file);
    preview.src = previewUrl;
    preview.hidden = false;
    $("#upload-prompt").hidden = true;
    $("#file-info").textContent = `${file.name} · ${(file.size / 1024).toFixed(0)} KiB · คลิกภาพเพื่อเปลี่ยนไฟล์`;
}
imageInput.addEventListener("change", loadImage);
preview.addEventListener("error", () => {
    if (!previewUrl) return;
    clearPreview(); imageInput.value = "";
    setStatus("ไม่สามารถอ่านภาพนี้ได้ กรุณาเลือกไฟล์ใหม่", "error");
});
preview.addEventListener("load", () => {
    if (preview.naturalWidth * preview.naturalHeight > 20_000_000) {
        clearPreview(); imageInput.value = "";
        setStatus("ภาพเกิน 20 ล้านพิกเซล กรุณาย่อภาพแล้วลองใหม่", "error");
    }
});
const dropZone = $("#drop-zone");
["dragenter", "dragover"].forEach(name => dropZone.addEventListener(name, event => {
    event.preventDefault(); if (!busy) dropZone.classList.add("dragging");
}));
["dragleave", "drop"].forEach(name => dropZone.addEventListener(name, event => {
    event.preventDefault(); dropZone.classList.remove("dragging");
}));
dropZone.addEventListener("drop", event => {
    if (busy) return;
    const files = event.dataTransfer.files;
    if (files.length !== 1) {setStatus("กรุณาเลือกภาพครั้งละหนึ่งไฟล์", "error"); return;}
    imageInput.files = files;
    loadImage();
});
$("#clear").addEventListener("click", () => {
    sourceInput.value = ""; imageInput.value = "";
    clearPreview(); updateCount(); resetResult();
});
function setBusy(value) {
    busy = value;
    [$("#extract"), $("#clear"), $("#sample"), sourceInput, imageInput, ...tabs].forEach(control => control.disabled = value);
    $("#cancel").hidden = !value;
    $("#extract-label").textContent = value ? "กำลังแปลงข้อมูล…" : "แปลงข้อมูล";
    $(".output-section").setAttribute("aria-busy", String(value));
    document.body.classList.toggle("is-running", value);
    $("#copy").disabled = value || !receiptData || demoResult;
    $("#download").disabled = value || !receiptData || demoResult;
}
function addLog(message, level = "info") {
    $("#log-empty").hidden = true;
    const li = document.createElement("li");
    const time = document.createElement("time");
    const text = document.createElement("span");
    const now = new Date();
    time.dateTime = now.toISOString();
    time.textContent = now.toLocaleTimeString("th-TH", {hour12: false});
    text.textContent = message;
    li.dataset.level = level;
    li.append(time, text); processLog.append(li);
    $("#log-count").textContent = `${processLog.children.length} รายการ`;
    processLog.scrollTop = processLog.scrollHeight;
}
function displayResult(result, demo) {
    if (result.document_type !== "receipt" || result.data === null) {
        clearOutput();
        $("#empty-title").textContent = result.document_type === "not_receipt" ? "เอกสารนี้ไม่ใช่ใบเสร็จร้านค้า" : "ยังอ่านเอกสารนี้ไม่ได้ชัดเจน";
        $("#empty-description").textContent = "ลองเลือกภาพใบเสร็จที่เห็นรายละเอียดครบ หรือวางข้อความจากต้นฉบับ";
        setStatus(result.reason, "rejected");
        return;
    }
    receiptData = result.data;
    demoResult = demo;
    for (const [field, value] of Object.entries(receiptData)) {
        const element = document.getElementById(`field-${field}`);
        if (!element) continue;
        element.classList.toggle("is-null", value === null);
        element.textContent = value === null ? "ไม่ระบุ" : field === "total" ? new Intl.NumberFormat("th-TH", {minimumFractionDigits: 2, maximumFractionDigits: 2}).format(value) : String(value);
    }
    resultBox.textContent = JSON.stringify(receiptData, null, 2);
    $("#empty-state").hidden = true;
    $("#receipt-summary").hidden = false;
    setStatus(demo ? "ผลจำลองสำหรับทดสอบหน้าจอ ไม่ใช่ข้อมูลจากใบเสร็จ" : "จัดข้อมูลแล้ว กรุณาตรวจเทียบกับใบเสร็จต้นฉบับ", "success");
}
$("#extract").addEventListener("click", async () => {
    if (busy) return;
    resetResult();
    const form = new FormData(); form.append("mode", mode);
    if (mode === "text") {
        const text = sourceInput.value.trim();
        if (!text) {setStatus("กรุณากรอกข้อความใบเสร็จก่อน", "error"); sourceInput.focus(); return;}
        form.append("text", text);
    } else {
        if (!imageInput.files[0]) {setStatus("กรุณาเลือกรูปใบเสร็จก่อน", "error"); imageInput.focus(); return;}
        form.append("image", imageInput.files[0]);
    }
    controller = new AbortController();
    setBusy(true); setStatus("กำลังส่งข้อมูล…", "busy");
    $("#empty-title").textContent = "กำลังอ่านใบเสร็จ";
    $("#empty-description").textContent = "ติดตามขั้นตอนได้จากบันทึกการทำงานด้านล่าง";
    addLog("ส่งข้อมูลเพื่อประมวลผล");
    try {
        const response = await fetch("/api/extract/stream", {method: "POST", body: form, signal: controller.signal});
        if (!response.ok) {
            let message = `คำขอไม่สำเร็จ (HTTP ${response.status})`;
            try {const body = await response.json(); if (typeof body.detail === "string") message = body.detail;} catch {}
            throw new Error(message);
        }
        if (!(response.headers.get("content-type") || "").includes("text/event-stream")) throw new Error("ระบบไม่ได้ส่งข้อมูลสถานะกลับมา กรุณาลองใหม่");
        await readSSE(response, event => {
            const prefix = event.demo ? "[จำลอง] " : "";
            if (event.type === "progress") {addLog(prefix + event.message); setStatus(prefix + event.message, "busy");}
            else if (event.type === "result") {displayResult(event.data, !!event.demo); addLog(prefix + "ได้รับผลลัพธ์แล้ว");}
            else if (event.type === "error") {
                clearOutput();
                $("#empty-title").textContent = "ยังแปลงข้อมูลไม่สำเร็จ";
                $("#empty-description").textContent = "ตรวจข้อความแจ้งเตือน แล้วลองอีกครั้ง";
                setStatus(event.message, "error"); addLog(prefix + event.message, "error");
            } else if (event.type === "done") addLog(prefix + "จบการทำงาน");
            if (event.demo) {
                $("#run-mode").hidden = false;
                $("#run-mode").textContent = "โหมดจำลอง: ไม่ได้เรียก AI และไม่ได้อ่านข้อมูลจากเอกสารนี้";
            }
        });
    } catch (error) {
        clearOutput();
        const cancelled = error.name === "AbortError";
        const message = cancelled ? "ยกเลิกการรอผลแล้ว" : (error.message || "การเชื่อมต่อมีปัญหา กรุณาลองใหม่");
        $("#empty-title").textContent = cancelled ? "ยกเลิกแล้ว" : "ยังแปลงข้อมูลไม่สำเร็จ";
        setStatus(message, cancelled ? "idle" : "error");
        addLog(message, cancelled ? "info" : "error");
    } finally {controller = null; setBusy(false);}
});
$("#cancel").addEventListener("click", () => controller?.abort());
$("#copy").addEventListener("click", async () => {
    if (!receiptData || demoResult || busy) return;
    try {await navigator.clipboard.writeText(resultBox.textContent); setStatus("คัดลอก JSON แล้ว", "success");}
    catch {$(".json-details").open = true; setStatus("คัดลอกอัตโนมัติไม่ได้ กรุณาเลือกข้อความ JSON แล้วคัดลอกด้วยตนเอง", "success");}
});
$("#download").addEventListener("click", () => {
    if (!receiptData || demoResult || busy) return;
    const url = URL.createObjectURL(new Blob([resultBox.textContent + "\n"], {type:"application/json;charset=utf-8"}));
    const link = document.createElement("a"); link.href = url; link.download = "messmation-receipt.json";
    document.body.append(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
});
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