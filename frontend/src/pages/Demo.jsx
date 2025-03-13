import { useEffect, useState, useRef } from "react";

const Demo = () => {
  const [messages, setMessages] = useState([]);
  const [ws, setWs] = useState(null);
  const audioRef = useRef(new Audio());

  useEffect(() => {
    let socket = new WebSocket("ws://127.0.0.1:8000/ws");

    socket.onopen = () => console.log("WebSocket connected");

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log(data.audio)
        setMessages((prev) => [...prev, data]);

        if (data.audio) {
          playAudio(data.audio);
        }
      } catch (error) {
        console.error("Error parsing message:", error);
      }
    };

    socket.onclose = () => {
      console.log("WebSocket closed, reconnecting...");
      setTimeout(() => {
        setWs(new WebSocket("ws://127.0.0.1:8000/ws"));
      }, 3000);
    };

    setWs(socket);

    return () => {
      if (socket) socket.close();
    };
  });

  const playAudio = (audioUrl) => {
    if (audioRef.current.src !== audioUrl) {
      audioRef.current.src = audioUrl;
      audioRef.current.load();
    }
    audioRef.current.play().catch((err) => console.error("Playback error:", err));
  };

  const pauseAudio = () => {
    audioRef.current.pause();
  };

  return (
    <div className="p-4">
      <h1 className="text-xl font-bold">Podcast Chat</h1>
      <div className="mt-4 space-y-2">
        {messages.map((msg, index) => (
          <div key={index} className="p-2 border rounded">
            <strong>{msg.speaker}:</strong> {msg.text}
          </div>
        ))}
      </div>
      <div className="mt-4">
        <button
          onClick={() => audioRef.current.play()}
          className="mr-2 px-4 py-2 bg-green-500 text-white rounded"
        >
          Play
        </button>
        <button
          onClick={pauseAudio}
          className="px-4 py-2 bg-red-500 text-white rounded"
        >
          Pause
        </button>
      </div>
    </div>
  );
};

export default Demo;
