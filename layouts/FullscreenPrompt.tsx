import React from "react";

interface FullscreenPromptProps {
  onAccept: () => void;
  onReject: () => void;
}

const FullscreenPrompt: React.FC<FullscreenPromptProps> = ({ onAccept, onReject }) => {
  return (
    <div className="fixed top-10 left-1/2 transform -translate-x-1/2 z-50 pointer-events-none mt-10">
      {/* Modal content */}
      <div className="bg-white p-4 rounded-lg shadow-lg text-center w-96 pointer-events-auto">
        <p className="text-lg font-semibold mb-4">
          The Interview Requires Fullscreen Mode To Proceed.
        </p>
        <button
          onClick={onAccept}
          className="bg-primary text-white px-4 py-2 rounded-md w-full mb-2 hover:bg-primary-dark transition"
        >
          Enter Fullscreen
        </button>
        <button
          onClick={onReject}
          className="bg-red-500 text-white px-4 py-2 rounded-md w-full hover:bg-red-600 transition"
        >
          Exit Interview
        </button>
      </div>
    </div>
  );
};

export default FullscreenPrompt;
