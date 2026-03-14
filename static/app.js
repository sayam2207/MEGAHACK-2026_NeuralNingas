/* ============================================================
   AI RC Car — Web Dashboard JavaScript
   WebSocket client, D-pad controls, sensor animations, AI chat
   ============================================================ */

// ---- WebSocket connection ----
const socket = io();

let msgCount = 0;
let currentMode = 'manual';

// ---- Connection status ----
socket.on('connect', () => {
    console.log('[WS] Connected');
    document.getElementById('connBadge').textContent = 'Connected';
    document.getElementById('connBadge').classList.add('connected');
});

socket.on('disconnect', () => {
    console.log('[WS] Disconnected');
    document.getElementById('connBadge').textContent = 'Disconnected';
    document.getElementById('connBadge').classList.remove('connected');
});

// ---- Sensor updates ----
socket.on('sensors', (data) => {
    updateSensor('Front', data.front);
    updateSensor('Back', data.back);
    updateSensor('Left', data.left);
    updateSensor('Right', data.right);

    // Mode & speed
    const mode = (data.mode || 'manual').toUpperCase();
    const speed = data.speed || 0;
    document.getElementById('infoMode').textContent = `⚙ Mode: ${mode}`;
    document.getElementById('infoSpeed').textContent = `⚡ Speed: ${speed} / 255`;

    // Update mode buttons
    updateModeButtons(mode.toLowerCase());

    // Car online status
    const carOnline = data.car_online || false;
    const mqttConnected = data.mqtt_connected || false;

    const dot = document.getElementById('statusDot');
    if (carOnline) {
        dot.classList.add('online');
        document.getElementById('sensorStatus').textContent = '● ACTIVE';
        document.getElementById('sensorStatus').style.color = 'var(--green)';
        document.getElementById('carStatus').textContent = '● Car: Online';
        document.getElementById('carStatus').style.color = 'var(--green)';
    } else {
        dot.classList.remove('online');
        document.getElementById('sensorStatus').textContent = '● WAITING';
        document.getElementById('sensorStatus').style.color = 'var(--text-muted)';
        document.getElementById('carStatus').textContent = '● Car: Offline';
        document.getElementById('carStatus').style.color = 'var(--text-muted)';
    }

    if (mqttConnected) {
        document.getElementById('mqttStatus').textContent = '● MQTT: Connected';
        document.getElementById('mqttStatus').style.color = 'var(--green)';
    } else {
        document.getElementById('mqttStatus').textContent = '● MQTT: Disconnected';
        document.getElementById('mqttStatus').style.color = 'var(--red)';
    }
});

function updateSensor(name, value) {
    const key = name.charAt(0).toUpperCase() + name.slice(1).toLowerCase();
    // Handle case variations
    const barEl = document.getElementById(`bar${key}`);
    const valEl = document.getElementById(`val${key}`);
    const iconEl = document.querySelector(`#sensor${key} .sensor-icon`);

    if (!barEl || !valEl) return;

    const v = value || 999;
    const pct = Math.max(2, Math.min(100, (v / 200) * 100));

    // Color based on distance
    let color;
    if (v < 15) color = 'var(--red)';
    else if (v < 25) color = 'var(--orange)';
    else if (v < 40) color = 'var(--yellow)';
    else color = 'var(--green)';

    barEl.style.width = `${pct}%`;
    barEl.style.backgroundColor = color;
    valEl.textContent = v < 999 ? `${v.toFixed(0)} cm` : '---';
    valEl.style.color = color;

    // Icon color change for danger
    if (iconEl) {
        iconEl.style.color = v < 35 ? color : 'var(--cyan)';
    }
}

// ---- D-Pad buttons ----
document.querySelectorAll('.dpad-btn, .speed-btn').forEach(btn => {
    const cmd = btn.dataset.cmd;
    if (!cmd) return;

    // Touch events (mobile)
    btn.addEventListener('touchstart', (e) => {
        e.preventDefault();
        sendCommand(cmd);
    });

    // Click events (desktop)
    btn.addEventListener('click', (e) => {
        sendCommand(cmd);
    });
});

function sendCommand(cmd) {
    socket.emit('command', { command: cmd });
    addChatMsg(`→ ${cmd}`, 'action');
}

// ---- Mode buttons ----
document.querySelectorAll('.mode-btn').forEach(btn => {
    const mode = btn.dataset.mode;
    btn.addEventListener('click', () => {
        socket.emit('mode', { mode: mode });
        addChatMsg(`→ Mode: ${mode.toUpperCase()}`, 'action');
    });
});

function updateModeButtons(mode) {
    if (mode === currentMode) return;
    currentMode = mode;
    document.querySelectorAll('.mode-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.mode === mode);
    });
}

// Initialize default mode
updateModeButtons('manual');

// ---- Chat ----
const chatLog = document.getElementById('chatLog');
const chatInput = document.getElementById('chatInput');
const chatSend = document.getElementById('chatSend');

chatSend.addEventListener('click', sendChat);
chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') sendChat();
});

function sendChat() {
    const text = chatInput.value.trim();
    if (!text) return;
    chatInput.value = '';
    addChatMsg(`You: ${text}`, 'you');
    addChatMsg('🤖 Thinking...', 'system');

    socket.emit('chat', { message: text });
}

// ---- Voice control (Web Speech API) ----
const chatMic = document.getElementById('chatMic');
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

if (SpeechRecognition && chatMic) {
    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-US';

    let isRecording = false;

    chatMic.addEventListener('mousedown', startVoiceControl);
    chatMic.addEventListener('touchstart', (e) => { e.preventDefault(); startVoiceControl(); });

    chatMic.addEventListener('mouseup', stopVoiceControl);
    chatMic.addEventListener('mouseleave', stopVoiceControl);
    chatMic.addEventListener('touchend', stopVoiceControl);
    chatMic.addEventListener('touchcancel', stopVoiceControl);

    function startVoiceControl() {
        if (isRecording) return;
        isRecording = true;
        chatMic.style.color = "var(--red)";
        chatMic.style.borderColor = "var(--red)";
        chatInput.placeholder = "Listening...";
        try {
            recognition.start();
            console.log("Voice control started");
        } catch (e) {
            console.error("Recognition already started: ", e);
        }
    }

    function stopVoiceControl() {
        if (!isRecording) return;
        isRecording = false;
        chatMic.style.color = "var(--text-muted)";
        chatMic.style.borderColor = "var(--border)";
        chatInput.placeholder = "Ask the AI or type a command...";
        try {
            recognition.stop();
            console.log("Voice control stopped");
        } catch (e) {}
    }

    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        console.log("Voice recognized: ", transcript);
        chatInput.value = transcript;
        sendChat(); // Auto-send the voice command
    };

    recognition.onerror = (event) => {
        console.error('Speech recognition error: ' + event.error);
        stopVoiceControl();
    };

} else if (chatMic) {
    // Browser doesn't support Web Speech API
    chatMic.style.display = 'none';
}

socket.on('chat_reply', (data) => {
    // Remove "Thinking..." message
    const msgs = chatLog.querySelectorAll('.msg.system');
    msgs.forEach(m => {
        if (m.textContent.includes('Thinking...')) m.remove();
    });

    if (data.action) {
        addChatMsg(`→ AI action: ${data.action}`, 'action');
    }
    addChatMsg(`🤖 ${data.reply}`, 'ai');
});

socket.on('command_ack', (data) => {
    // Command acknowledged
});

function addChatMsg(text, cls = '') {
    const div = document.createElement('div');
    div.className = `msg ${cls}`;
    const now = new Date();
    const ts = now.toTimeString().slice(0, 8);
    div.textContent = `[${ts}] ${text}`;
    chatLog.appendChild(div);
    chatLog.scrollTop = chatLog.scrollHeight;

    msgCount++;
    document.getElementById('chatCount').textContent = `${msgCount} messages`;
}

// ---- Keyboard shortcuts (desktop) ----
document.addEventListener('keydown', (e) => {
    // Don't intercept when typing in chat
    if (document.activeElement === chatInput) return;

    const keyMap = {
        'w': 'forward', 'arrowup': 'forward',
        's': 'backward', 'arrowdown': 'backward',
        'a': 'left', 'arrowleft': 'left',
        'd': 'right', 'arrowright': 'right',
        'x': 'stop', ' ': 'stop',
        'f': 'speed_full',
        'g': 'speed_slow',
    };

    const cmd = keyMap[e.key.toLowerCase()];
    if (cmd) {
        e.preventDefault();
        sendCommand(cmd);
    }
});

// ---- Initial message ----
addChatMsg('🌐 Web Dashboard connected!', 'system');
addChatMsg('Use D-pad or keyboard (WASD/Arrows) to control.', 'system');
