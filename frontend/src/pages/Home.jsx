import React, { useState, useRef, useEffect } from "react";

const Home = () => {
  const [input, setInput] = useState("");
  const [file, setFile] = useState(null);
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [audioStream, setAudioStream] = useState(null);
  const [audioBlob, setAudioBlob] = useState(null);
  const [mediaRecorder, setMediaRecorder] = useState(null);
  const [silenceTimer, setSilenceTimer] = useState(null);
  const [silenceStart, setSilenceStart] = useState(null);
  const audioRef = useRef(null);
  const messagesEndRef = useRef(null);
  const audioChunks = useRef([]);
  const [alexAudio, setAlexAudio] = useState(null);
  const [emmaAudio, setEmmaAudio] = useState(null);
  const [isAudioPlaying, setIsAudioPlaying] = useState(false); // New state to track audio playback

  const currentAudioRef = useRef(null);

  useEffect(() => {
    // Add welcome message on component mount
    setMessages([
      {
        type: "ai",
        content:
          "Welcome to InfernoCastAI! I'm your podcast assistant ready to analyze documents, discuss topics, or answer questions. Upload a file or type your query on the left to begin our conversation.",
        time: new Date().toLocaleTimeString(),
      },
    ]);
  }, []);

  useEffect(() => {
    // Scroll to bottom when messages update
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleInputChange = (e) => {
    setInput(e.target.value);
  };

  const handleFileChange = (e) => {
    if (e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!input && !file) return;

    const newMessage = {
      type: "user",
      content: input || file?.name || "Uploaded file",
      time: new Date().toLocaleTimeString(),
    };

    setMessages((prev) => [...prev, newMessage]);
    setIsLoading(true);

    try {
      let response;

      if (input) {
        // Sending text input to /process-text
        response = await fetch("http://localhost:8000/process-text", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ text: input }),
        });
      } else if (file) {
        // Sending file input to /process-file
        const formData = new FormData();
        formData.append("file", file);

        response = await fetch("http://localhost:8000/process-file", {
          method: "POST",
          body: formData,
        });
      }

      const result = await response.json();
      console.log(result);
      if (!response.ok) throw new Error(result.detail);

      // Add AI response to messages
      setMessages((prev) => [
        ...prev,
        {
          type: "ai",
          content: result.summary || "I processed your request.",
          time: new Date().toLocaleTimeString(),
        },
      ]);
    } catch (error) {
      console.error("Error:", error);
      setMessages((prev) => [
        ...prev,
        {
          type: "ai",
          content:
            "Sorry, I encountered an error processing your request. Please try again.",
          time: new Date().toLocaleTimeString(),
        },
      ]);
    } finally {
      setIsLoading(false);
      setInput("");
      setFile(null);
    }
  };
  const [socket, setSocket] = useState(null);

  const startPodcast = () => {
    if (socket && socket.readyState === WebSocket.OPEN) {
      console.log("WebSocket is already connected.");
      return;
    }
  
    const newSocket = new WebSocket("ws://127.0.0.1:8000/ws");
  
    newSocket.onopen = () => {
      console.log("WebSocket connection established");
      // newSocket.send(JSON.stringify({ message: "Start Podcast" }));
    };
  
    newSocket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log("received: ", data.audio);
        console.log(data.speaker);
  
        if (data.audio) {
          const audio = new Audio(data.audio);
          setIsAudioPlaying(true); // Set audio playing to true
  
          audio.onended = () => {
            setIsAudioPlaying(false); // Set audio playing to false when ended
            console.log("Audio playback completed.");
  
            // Send a "done" message to the backend after audio finishes
            if (newSocket && newSocket.readyState === WebSocket.OPEN) {
              newSocket.send(JSON.stringify({ message: "Audio playback done" }));
            }
          };
  
          audio.play();
        }
      } catch (error) {
        console.error("Error processing WebSocket message:", error);
      }
    };
  
    newSocket.onclose = (event) => {
      console.log("WebSocket closed:", event.reason);
    };
  
    newSocket.onerror = (error) => {
      console.error("WebSocket Error:", error);
    };
  
    setSocket(newSocket); // Store the socket in state
  };
  
  useEffect(() => {
    return () => {
      if (socket) {
        socket.close();
      }
    };
  }, [socket]);
  

  return (
    <div className="flex h-screen bg-gray-900 text-gray-200 overflow-hidden">
      {/* Left Panel - 40% width */}
      <div className="w-2/5 border-r-2 border-orange-500 flex flex-col p-6 bg-gradient-to-b from-gray-900 to-gray-800">
        <div className="flex items-center mb-8">
          <div className="flex items-center justify-center h-12 w-12 rounded-full bg-orange-600 mr-3">
            <svg
              className="w-7 h-7 text-white"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"
              ></path>
            </svg>
          </div>
          <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-orange-500 to-red-600">
            InfernoCastAI
          </h1>
        </div>

        <p className="text-gray-400 mb-6 text-sm">
          Your intelligent podcast assistant. Upload documents or ask questions
          to start a conversation.
        </p>

        <form onSubmit={handleSubmit} className="flex flex-col flex-grow">
          <div className="flex-grow">
            <label className="block mb-2 text-sm font-medium text-gray-300">
              What would you like to discuss?
            </label>
            <textarea
              className="w-full h-64 p-4 bg-gray-800 border border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-orange-500 resize-none shadow-lg"
              placeholder="Type your question or prompt here..."
              value={input}
              onChange={handleInputChange}
            />

            <div className="mt-6">
              <label className="block mb-2 text-sm font-medium text-gray-300">
                Or upload a file (PDF, audio, document)
              </label>
              <div className="border-2 border-dashed border-gray-700 rounded-lg p-4 hover:border-orange-500 transition-colors duration-200">
                <input
                  type="file"
                  accept=".pdf,.doc,.docx,.txt,.mp3,.wav"
                  onChange={handleFileChange}
                  className="block w-full text-sm text-gray-400 cursor-pointer bg-transparent focus:outline-none"
                />
                <p className="text-xs text-gray-500 mt-2">
                  Supported formats: PDF, DOC, DOCX, TXT, MP3, WAV
                </p>
              </div>
              {file && (
                <div className="mt-3 p-2 bg-gray-800 rounded-lg text-sm flex items-center">
                  <svg
                    className="w-5 h-5 text-orange-500 mr-2"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="2"
                      d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                    ></path>
                  </svg>
                  <span className="text-orange-400 truncate">{file.name}</span>
                </div>
              )}
            </div>
          </div>

          <button
            type="submit"
            disabled={(!input && !file) || isLoading}
            className={`mt-6 py-3 px-4 rounded-lg font-medium ${
              (!input && !file) || isLoading
                ? "bg-gray-700 text-gray-500 cursor-not-allowed"
                : "bg-gradient-to-r from-orange-500 to-red-600 hover:from-orange-600 hover:to-red-700 text-white shadow-lg"
            } transition duration-200`}
          >
            {isLoading ? (
              <span className="flex items-center justify-center">
                <svg
                  className="animate-spin -ml-1 mr-2 h-4 w-4 text-white"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  ></circle>
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  ></path>
                </svg>
                Processing...
              </span>
            ) : (
              <span className="flex items-center justify-center">
                <svg
                  className="mr-2 h-4 w-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M14 5l7 7m0 0l-7 7m7-7H3"
                  ></path>
                </svg>
                Submit
              </span>
            )}
          </button>
        </form>
      </div>

      {/* Right Panel - 60% width */}
      <div className="w-3/5 flex flex-col h-full bg-gradient-to-b from-gray-800 to-gray-900">
        {/* Header */}
        <div className="p-4 border-b border-gray-700 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-orange-400">
            Conversation
          </h2>
          <div className="flex items-center text-sm text-gray-400">
            <span className="flex items-center mr-4">
              <span className="h-2 w-2 rounded-full bg-green-500 mr-1"></span>
              Online
            </span>
            <svg
              className="w-5 h-5 text-gray-500 hover:text-gray-300 cursor-pointer"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
              ></path>
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
              ></path>
            </svg>
          </div>
        </div>

        {/* Messages Area */}
        <div className="flex-grow overflow-y-auto p-5">
          <div className="space-y-6">
            {messages.map((message, index) => (
              <div
                key={index}
                className={`p-4 rounded-lg shadow-md ${
                  message.type === "user"
                    ? "bg-gray-700 ml-16 border-l-4 border-blue-500"
                    : message.type === "system"
                    ? "bg-gray-700 border border-gray-600 text-center max-w-md mx-auto"
                    : "bg-gradient-to-r from-gray-800 to-gray-900 mr-16 border-l-4 border-orange-500"
                }`}
              >
                <div className="flex justify-between items-center mb-2">
                  <div className="flex items-center">
                    {message.type === "user" ? (
                      <div className="h-8 w-8 rounded-full bg-blue-700 flex items-center justify-center mr-2">
                        <svg
                          className="w-4 h-4 text-blue-300"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                          xmlns="http://www.w3.org/2000/svg"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth="2"
                            d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                          ></path>
                        </svg>
                      </div>
                    ) : message.type === "system" ? (
                      <div className="h-8 w-8 rounded-full bg-gray-600 flex items-center justify-center mr-2">
                        <svg
                          className="w-4 h-4 text-gray-300"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                          xmlns="http://www.w3.org/2000/svg"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth="2"
                            d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                          ></path>
                        </svg>
                      </div>
                    ) : (
                      <div className="h-8 w-8 rounded-full bg-gradient-to-r from-orange-500 to-red-600 flex items-center justify-center mr-2">
                        <svg
                          className="w-4 h-4 text-white"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                          xmlns="http://www.w3.org/2000/svg"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth="2"
                            d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
                          ></path>
                        </svg>
                      </div>
                    )}
                    <span className="font-bold text-sm">
                      {message.type === "user"
                        ? "You"
                        : message.type === "system"
                        ? "System"
                        : "InfernoCastAI"}
                    </span>
                  </div>
                  <span className="text-xs text-gray-400">{message.time}</span>
                </div>
                <p className="ml-10">{message.content}</p>
                {message.audioUrl && (
                  <div className="mt-3 ml-10">
                    <div className="flex items-center">
                      <button
                        className="flex items-center justify-center text-xs bg-orange-600 hover:bg-orange-700 text-white px-3 py-1 rounded"
                        onClick={() =>
                          audioRef.current && audioRef.current.play()
                        }
                      >
                        <svg
                          className="w-4 h-4 mr-1"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                          xmlns="http://www.w3.org/2000/svg"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth="2"
                            d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"
                          ></path>
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth="2"
                            d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                          ></path>
                        </svg>
                        Play Audio
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ))}

            {isLoading && (
              <div className="flex justify-center items-center p-4">
                <div className="loader">
                  <div className="flex space-x-2">
                    <div className="h-3 w-3 bg-orange-500 rounded-full animate-bounce"></div>
                    <div
                      className="h-3 w-3 bg-orange-500 rounded-full animate-bounce"
                      style={{ animationDelay: "0.2s" }}
                    ></div>
                    <div
                      className="h-3 w-3 bg-orange-500 rounded-full animate-bounce"
                      style={{ animationDelay: "0.4s" }}
                    ></div>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Voice Input Buttons */}
        <div className="p-4 border-t border-gray-700 bg-gray-800 flex space-x-4">
          {/* Start Podcast Button */}
          <button
            onClick={startPodcast}
            disabled={isAudioPlaying} // Disable the button while audio is playing
            className={`w-1/2 py-3 px-4 rounded-lg font-medium flex items-center justify-center ${
              isAudioPlaying
                ? "bg-gray-600 text-gray-400 cursor-not-allowed" // Disabled button styles
                : "bg-gradient-to-r from-purple-500 to-purple-600 hover:from-purple-600 hover:to-purple-700 text-white transition duration-200 shadow-lg"
            }`}
          >
            <svg
              className="w-5 h-5 mr-2"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M15 10l4.553 4.553a1 1 0 010 1.414L15 20M9 10l-4.553 4.553a1 1 0 000 1.414L9 20"
              ></path>
            </svg>
            Start Podcast
          </button>

          {/* Join Conversation Button */}
          <button
            className={`w-1/2 py-3 px-4 rounded-lg font-medium flex items-center justify-center ${
              isRecording
                ? "bg-red-600 hover:bg-red-700 text-white animate-pulse"
                : "bg-gradient-to-r from-green-500 to-green-600 hover:from-green-600 hover:to-green-700 text-white"
            } transition duration-200 shadow-lg`}
          >
            {isRecording ? (
              <span className="flex items-center">
                <svg
                  className="w-5 h-5 mr-2"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z"
                  ></path>
                </svg>
                Recording... (Stops after 5s of silence)
              </span>
            ) : (
              <span className="flex items-center">
                <svg
                  className="w-5 h-5 mr-2"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"
                  ></path>
                </svg>
                Join Conversation
              </span>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

export default Home;
