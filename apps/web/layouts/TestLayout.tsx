"use client";

import React, { ReactNode, useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import FullscreenPrompt from "./FullscreenPrompt";
import ExitWarningModal from "./ExitWarningModal";
import { Header } from "@/components/Header";

interface TestLayoutProps {
  children: ReactNode;
}

const TestLayout: React.FC<TestLayoutProps> = ({ children }) => {
  const [warnings, setWarnings] = useState<number>(0);
  const [isFullscreenPromptVisible, setFullscreenPromptVisible] = useState<boolean>(false);
  const [isWarningVisible, setWarningVisible] = useState<boolean>(false);
  const router = useRouter();
  const [username, setUsername] = useState<string>("User");
  const [isPopupVisible, setPopupVisible] = useState<boolean>(false);
  const [showModal, setShowModal] = useState<boolean>(false);
  const [isNavigatingBack, setIsNavigatingBack] = useState<boolean>(false);

  useEffect(() => {
    setFullscreenPromptVisible(!document.fullscreenElement);
  }, []);

  useEffect(() => {
    const fetchCookies = async () => {
      try {
        const response = await fetch("/api/getCookies");
        const data = await response.json();
        setUsername(data.candidateName);
      
      } catch (error) {
       
      }
    };

    fetchCookies();
  }, []);

  const handleExit = () => {
    setPopupVisible(true);
  };

  const handleCancel = () => {
    setPopupVisible(false);
  };

  const handleConfirm = async () => {
    setPopupVisible(false);
    await fetch("/api/auth/logout",{
      method: "POST"
    })
    .catch((err) => {
    })
      
    router.push("/Interview/Feedback");
  };

  const enterFullscreen = (): void => {
    const elem = document.documentElement;
    if (elem.requestFullscreen) {
      elem.requestFullscreen().catch((err) => {
        //will add toast message
      });
    } else if ((elem as any).webkitRequestFullscreen) {
      (elem as any).webkitRequestFullscreen();
    } else if ((elem as any).msRequestFullscreen) {
      (elem as any).msRequestFullscreen();
    }
  };

  const handleInitialPrompt = (accept: boolean) => {
    setFullscreenPromptVisible(false);
    if (accept) {
      enterFullscreen();
    } else {
      router.push("/Interview/Feedback");                                         // Redirect to feedback page if "No"
    }
  };

  useEffect(() => {
    const handleFullscreenChange = (): void => {
      if (!document.fullscreenElement) {
        setWarnings((prev) => prev + 1);
        setWarningVisible(true);
      } else {
        setWarningVisible(false);
      }
    };

    document.addEventListener("fullscreenchange", handleFullscreenChange);

    return () => {
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
    };
  }, []);

  useEffect(() => {
    if (warnings >= 3) {
      alert("You have exited fullscreen mode too many times. The test is terminated.");
      router.push("/Interview/Feedback");
    }
  }, [warnings, router]);

  const handleReenterFullscreen = () => {
    setWarningVisible(false);
    enterFullscreen();
  };
  useEffect(() => {
    window.history.pushState(null, document.title, window.location.href);

    const handlePopState = () => {
      if (isNavigatingBack) return;

      setIsNavigatingBack(true);
      setShowModal(true);
      window.history.pushState(null, document.title, window.location.href); // Prevent actual back navigation
    };

    window.addEventListener("popstate", handlePopState);

    return () => {
      window.removeEventListener("popstate", handlePopState);
    };
  }, [isNavigatingBack]);


  const handleCancelModal = () => {
    setIsNavigatingBack(false);
    setShowModal(false);
  };

  return (
    <div>
      {isFullscreenPromptVisible && (
        <FullscreenPrompt onAccept={() => handleInitialPrompt(true)} onReject={() => handleInitialPrompt(false)} />
      )}
  
      {isWarningVisible && warnings < 3 && (
        <ExitWarningModal onReenterFullscreen={handleReenterFullscreen} />
      )}

      {!isFullscreenPromptVisible && <div>
        <Header username={username} onExit={handleExit}/>
        {isPopupVisible && (
        <div className="fixed inset-0 flex items-center justify-center bg-black bg-opacity-50 z-10">
          <div className="bg-white p-6 rounded-lg shadow-lg text-center">
            <h2 className="text-lg font-semibold text-gray-800">
              Are you sure you want to end the interview?
            </h2>
            <div className="mt-4 flex justify-center space-x-4">
              <button
                onClick={handleCancel}
                className="px-4 py-2 bg-gray-300 rounded-lg hover:bg-gray-400"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirm}
                className="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600"
              >
                Submit and Exit
              </button>
            </div>
          </div>
        </div>
      )}

      <div>
      {showModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 backdrop-blur-sm">
                  <div className="bg-white rounded-lg shadow-lg p-6 max-w-md text-center">
                    <h2 className="text-xl font-semibold mb-4">Warning</h2>
                    <p className="text-gray-700 mb-6">
                      Navigating back will remove you from the test.
                    </p>
                    <button
                      onClick={handleCancelModal}
                      className="px-4 py-2 bg-blue-500 text-white rounded-lg shadow hover:bg-blue-600"
                    >
                      Stay Here
                    </button>
                  </div>
                </div>
      )}

      </div>

        {children}
        </div>}
    </div>
  );
};

export default TestLayout;
