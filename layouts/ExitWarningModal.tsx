import React from "react";
import { Button } from "@/components/ui/button";

interface ExitWarningModalProps {
  onReenterFullscreen: () => void;
}

const ExitWarningModal: React.FC<ExitWarningModalProps> = ({ onReenterFullscreen }) => {
  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-md flex items-center justify-center z-50 pointer-events-none">
      <div className="bg-white p-6 border border-black rounded-lg shadow-lg text-black text-center w-80 pointer-events-auto">
        <p className="text-xl font-semibold mb-4">You exited fullscreen mode!</p>
        <p className="mb-4">If you leave fullscreen, you will be exited from the test.</p>
        <Button
          onClick={onReenterFullscreen}
          className="bg-primary text-white px-6 py-2 rounded-md transition"
        >
          Re-enter Fullscreen
        </Button>
      </div>
    </div>
  );
};

export default ExitWarningModal;
