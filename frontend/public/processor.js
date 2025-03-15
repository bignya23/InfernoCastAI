class AudioProcessor extends AudioWorkletProcessor {
    process(inputs) {
        const input = inputs[0];
        if (input.length > 0) {
            const rawData = input[0];
            const int16Data = convertFloat32ToInt16(rawData);
            this.port.postMessage(int16Data);
        }
        return true;
    }
}

// Convert Float32 PCM audio to Int16 PCM (required for WebSocket transmission)
function convertFloat32ToInt16(buffer) {
    let int16Array = new Int16Array(buffer.length);
    for (let i = 0; i < buffer.length; i++) {
        int16Array[i] = Math.max(-32768, Math.min(32767, buffer[i] * 32768));
    }
    return int16Array.buffer;
}

registerProcessor("audio-processor", AudioProcessor);