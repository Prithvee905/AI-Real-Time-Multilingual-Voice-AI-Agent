/**
 * Voice AI Agent — Frontend Application
 * Handles WebSocket connection, audio recording, and UI interactions.
 */

class VoiceAIAgent {
    constructor() {
        // ─── State ───────────────────────────────────────
        this.ws = null;
        this.isConnected = false;
        this.isRecording = false;
        this.isProcessing = false;
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.sessionId = this.generateId();

        // ─── DOM References ──────────────────────────────
        this.chatMessages = document.getElementById('chatMessages');
        this.textInput = document.getElementById('textInput');
        this.sendBtn = document.getElementById('sendBtn');
        this.voiceBtn = document.getElementById('voiceBtn');
        this.connectBtn = document.getElementById('connectBtn');
        this.statusBadge = document.getElementById('statusBadge');
        this.statusText = document.getElementById('statusText');
        this.visualizer = document.getElementById('voiceVisualizer');
        this.latencyDisplay = document.getElementById('latencyDisplay');

        // ─── Settings ────────────────────────────────────
        this.patientId = document.getElementById('patientId');
        this.patientName = document.getElementById('patientName');
        this.languageSelect = document.getElementById('languageSelect');

        // ─── Init ────────────────────────────────────────
        this.bindEvents();
        this.addSystemMessage('Welcome! Configure your settings and click "Connect" to start a voice conversation.');
    }

    // ─── Utilities ───────────────────────────────────────────

    generateId() {
        return 'sess_' + Math.random().toString(36).substring(2, 10);
    }

    getTimestamp() {
        return new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    }

    // ─── Event Bindings ──────────────────────────────────────

    bindEvents() {
        this.connectBtn.addEventListener('click', () => this.toggleConnection());
        this.sendBtn.addEventListener('click', () => this.sendTextMessage());
        this.voiceBtn.addEventListener('click', () => this.toggleRecording());

        this.textInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendTextMessage();
            }
        });

        // Quick action buttons
        document.querySelectorAll('.quick-action-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const text = e.currentTarget.dataset.text;
                if (text) {
                    this.textInput.value = text;
                    this.sendTextMessage();
                }
            });
        });
    }

    // ─── WebSocket Connection ────────────────────────────────

    toggleConnection() {
        if (this.isConnected) {
            this.disconnect();
        } else {
            this.connect();
        }
    }

    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/voice/${this.sessionId}`;

        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            this.isConnected = true;
            this.updateConnectionUI(true);
            this.addSystemMessage('🟢 Connected to Voice AI Agent. You can now speak or type your message.');
        };

        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleServerMessage(data);
        };

        this.ws.onclose = () => {
            this.isConnected = false;
            this.updateConnectionUI(false);
            this.addSystemMessage('🔴 Disconnected from server.');
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.addSystemMessage('⚠️ Connection error. Please try again.');
        };
    }

    disconnect() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        this.isConnected = false;
        this.updateConnectionUI(false);
    }

    updateConnectionUI(connected) {
        if (connected) {
            this.statusBadge.classList.remove('disconnected');
            this.statusText.textContent = 'Connected';
            this.connectBtn.textContent = '⏏ Disconnect';
            this.connectBtn.classList.remove('connect');
            this.connectBtn.classList.add('disconnect');
            this.sendBtn.disabled = false;
        } else {
            this.statusBadge.classList.add('disconnected');
            this.statusText.textContent = 'Disconnected';
            this.connectBtn.textContent = '🔌 Connect';
            this.connectBtn.classList.remove('disconnect');
            this.connectBtn.classList.add('connect');
            this.sendBtn.disabled = true;
        }
    }

    // ─── Message Handling ────────────────────────────────────

    handleServerMessage(data) {
        switch (data.type) {
            case 'transcription':
                // Show user's transcribed speech
                // Already shown when sent text
                break;

            case 'response':
                this.removeTypingIndicator();
                this.isProcessing = false;
                this.voiceBtn.classList.remove('processing');

                // Add assistant message
                this.addMessage('assistant', data.text, data.language);

                // Play audio if available
                if (data.audio) {
                    this.playAudio(data.audio, data.audio_format || 'mp3');
                }

                // Update latency display
                if (data.latency) {
                    this.updateLatencyDisplay(data.latency);
                }
                break;

            case 'error':
                this.removeTypingIndicator();
                this.isProcessing = false;
                this.voiceBtn.classList.remove('processing');
                this.addSystemMessage(`⚠️ ${data.message}`);
                break;
        }
    }

    // ─── Text Messages ───────────────────────────────────────

    sendTextMessage() {
        const text = this.textInput.value.trim();
        if (!text || !this.isConnected || this.isProcessing) return;

        // Add user message to UI
        this.addMessage('user', text, this.languageSelect.value);

        // Send to server
        this.ws.send(JSON.stringify({
            type: 'text',
            text: text,
            patient_id: this.patientId.value || 'PATIENT_001',
            patient_name: this.patientName.value || 'Patient',
            language: this.languageSelect.value
        }));

        this.textInput.value = '';
        this.isProcessing = true;
        this.showTypingIndicator();
    }

    // ─── Voice Recording ─────────────────────────────────────

    async toggleRecording() {
        if (!this.isConnected) {
            this.addSystemMessage('⚠️ Please connect first.');
            return;
        }

        if (this.isRecording) {
            this.stopRecording();
        } else {
            await this.startRecording();
        }
    }

    async startRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    sampleRate: 16000,
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true
                }
            });

            this.mediaRecorder = new MediaRecorder(stream, {
                mimeType: 'audio/webm;codecs=opus'
            });

            this.audioChunks = [];

            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    this.audioChunks.push(event.data);
                }
            };

            this.mediaRecorder.onstop = () => {
                const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
                this.sendAudioData(audioBlob);
                stream.getTracks().forEach(track => track.stop());
            };

            this.mediaRecorder.start();
            this.isRecording = true;
            this.voiceBtn.classList.add('recording');
            this.voiceBtn.innerHTML = '⏹';
            this.visualizer.classList.add('active');

        } catch (error) {
            console.error('Microphone error:', error);
            this.addSystemMessage('⚠️ Could not access microphone. Please check permissions.');
        }
    }

    stopRecording() {
        if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
            this.mediaRecorder.stop();
        }
        this.isRecording = false;
        this.voiceBtn.classList.remove('recording');
        this.voiceBtn.innerHTML = '🎤';
        this.visualizer.classList.remove('active');
    }

    async sendAudioData(audioBlob) {
        this.isProcessing = true;
        this.voiceBtn.classList.add('processing');
        this.showTypingIndicator();

        const arrayBuffer = await audioBlob.arrayBuffer();
        const base64Audio = btoa(String.fromCharCode(...new Uint8Array(arrayBuffer)));

        this.addMessage('user', '🎤 [Voice message]', this.languageSelect.value);

        this.ws.send(JSON.stringify({
            type: 'audio',
            data: base64Audio,
            format: 'webm',
            patient_id: this.patientId.value || 'PATIENT_001',
            patient_name: this.patientName.value || 'Patient',
            language: this.languageSelect.value
        }));
    }

    // ─── Audio Playback ──────────────────────────────────────

    playAudio(base64Audio, format = 'mp3') {
        try {
            const binaryStr = atob(base64Audio);
            const bytes = new Uint8Array(binaryStr.length);
            for (let i = 0; i < binaryStr.length; i++) {
                bytes[i] = binaryStr.charCodeAt(i);
            }
            const audioBlob = new Blob([bytes], { type: `audio/${format}` });
            const audioUrl = URL.createObjectURL(audioBlob);
            const audio = new Audio(audioUrl);
            audio.play().catch(err => console.warn('Audio playback error:', err));
        } catch (error) {
            console.error('Audio playback error:', error);
        }
    }

    // ─── UI Methods ──────────────────────────────────────────

    addMessage(role, text, language = 'en') {
        const langNames = { en: 'English', hi: 'Hindi', ta: 'Tamil' };
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${role}`;

        const avatarIcon = role === 'user' ? '👤' : '🤖';

        msgDiv.innerHTML = `
            <div class="message-avatar">${avatarIcon}</div>
            <div>
                <div class="message-content">${this.escapeHtml(text)}</div>
                <div class="message-meta">
                    <span>${this.getTimestamp()}</span>
                    <span class="message-lang">${langNames[language] || language}</span>
                </div>
            </div>
        `;

        this.chatMessages.appendChild(msgDiv);
        this.scrollToBottom();
    }

    addSystemMessage(text) {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'message system';
        msgDiv.innerHTML = `
            <div class="message-content">${text}</div>
        `;
        this.chatMessages.appendChild(msgDiv);
        this.scrollToBottom();
    }

    showTypingIndicator() {
        const existingIndicator = document.getElementById('typingIndicator');
        if (existingIndicator) return;

        const indicator = document.createElement('div');
        indicator.id = 'typingIndicator';
        indicator.className = 'message assistant';
        indicator.innerHTML = `
            <div class="message-avatar">🤖</div>
            <div class="message-content">
                <div class="typing-indicator">
                    <span></span><span></span><span></span>
                </div>
            </div>
        `;
        this.chatMessages.appendChild(indicator);
        this.scrollToBottom();
    }

    removeTypingIndicator() {
        const indicator = document.getElementById('typingIndicator');
        if (indicator) indicator.remove();
    }

    updateLatencyDisplay(latency) {
        const stages = latency.stages || {};
        const total = latency.total_ms || 0;
        const withinTarget = latency.within_target;

        let html = '';

        const stageIcons = {
            'speech_to_text': '🎤',
            'language_detection': '🌐',
            'agent_reasoning': '🤖',
            'text_to_speech': '🔊'
        };

        const stageNames = {
            'speech_to_text': 'Speech → Text',
            'language_detection': 'Language Detection',
            'agent_reasoning': 'AI Reasoning',
            'text_to_speech': 'Text → Speech'
        };

        for (const [stage, ms] of Object.entries(stages)) {
            const icon = stageIcons[stage] || '⚡';
            const name = stageNames[stage] || stage;
            const speedClass = ms < 100 ? 'fast' : ms < 300 ? 'medium' : 'slow';

            html += `
                <div class="latency-bar">
                    <span class="stage">${icon} ${name}</span>
                    <span class="time ${speedClass}">${ms.toFixed(0)}ms</span>
                </div>
            `;
        }

        html += `
            <div class="latency-total">
                <span class="label">Total Latency</span>
                <span class="value ${withinTarget ? 'within-target' : 'over-target'}">${total.toFixed(0)}ms</span>
            </div>
            <div class="latency-target">Target: < 450ms ${withinTarget ? '✅' : '⚠️'}</div>
        `;

        this.latencyDisplay.innerHTML = html;
    }

    scrollToBottom() {
        requestAnimationFrame(() => {
            this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
        });
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// ─── Initialize on DOM Ready ─────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    window.voiceAgent = new VoiceAIAgent();
});
