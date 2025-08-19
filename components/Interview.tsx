"use client";

import { StartAvatarResponse } from "@heygen/streaming-avatar"
import { FaTelegramPlane } from "react-icons/fa"
import { useState, useEffect, useRef } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { useRouter } from "next/navigation"
import StreamingAvatar, {
  AvatarQuality,
  StreamingEvents, TaskMode, TaskType, VoiceEmotion,
} from "@heygen/streaming-avatar";
import { useToast } from "@/hooks/use-toast"
import Loader from '@/images/CandidateLoader.gif'
import Image from "next/image"

export default function Interview() {
    const [isLoading, setLoading] = useState<boolean>(false);
    const [inputText, setInputText] = useState<string>("");
    const [transcript, setTranscript] = useState<string>("");
    const [isListening, setIsListening] = useState<boolean>(false);
    const recognitionRef = useRef<SpeechRecognition | null>(null);
    const textareaRef = useRef<HTMLTextAreaElement | null>(null);
    const [isMessageFlag, setIsMessageFlag] = useState<number>(0);
    const [startTime, setStartTime] = useState<number | null>(null);
    const [timeLeft, setTimeLeft] = useState<number>(30 * 60 * 1000);
    const [isButtonDisabled, setButtonDisabled] = useState<boolean>(true);
    const [avatarName, setAvatarName] = useState<string>();
    const [avatarVoice, setAvatarVoice] = useState<string>();
    const [skills, setSkills] = useState<string>();
    const [questionCount, setQuestionCount] = useState<number>(0);

    // For stream
    const [isLoadingSession, setIsLoadingSession] = useState<boolean>(false);
    const [isLoadingRepeat, setIsLoadingRepeat] = useState<boolean>(false);
    const [stream, setStream] = useState<MediaStream | undefined>();
    const [debug, setDebug] = useState<string>("");
    const [data, setData] = useState<StartAvatarResponse>();
    const mediaStream = useRef<HTMLVideoElement | null>(null);
    const avatar = useRef<StreamingAvatar | null>(null);
    const initialText : string = "Hello My name is Taara and welcome to round 1 interview of JMAN group for the position of software engineer. We would start with your introduction so go ahead and introduce yourself." 
    const [messages, setMessages] = useState<
      { id: number; text: string; isUser: boolean }[]
    >([]);
    const router = useRouter();
    const { toast } = useToast();

    const [candidateId, setCandidateId] = useState<number | null>(null);

    //to fetch the cookies
    useEffect(() => {
      const fetchCookies = async () => {
        try {
          const response = await fetch("/api/getCookies");
          const data = await response.json();
          setCandidateId(data.candidateId);
          setAvatarName(data.avatar);
          setAvatarVoice(data.voice);
          setSkills(data.skills);
          getStartTime(data.candidateId)
        } catch (error) {
        }
      };
  
      fetchCookies();
    }, []);

    const [isModalVisible, setModalVisible] = useState(true); // State to control start interview modal visibility
  
    useEffect(() => {
      async function onStart() {
          if (stream !== undefined) {
            await avatar.current?.closeVoiceChat();
            await endSession();
          }              
      }
      onStart();
    }, []);

  async function getStartTime(candidateID : number) {
    await fetch("/api/getInitialTime",{
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ 
        candidate_id: candidateID
      }),
    })
    .then((res) => res.json())
    .then((res) => {
      const fetchedTime = new Date(res.startTime).getTime();
      setStartTime(fetchedTime);

      const now = Date.now();
      const elapsed = now - fetchedTime;
      const initialRemaining = Math.max(30 * 60 * 1000 - elapsed, 0);
      setTimeLeft(initialRemaining);
    })
    .catch((err) => {
      toast({
        variant: "destructive",
        title: "Server Error",
        description: "There's some issue on our server! Please try starting interview again. If issue persists contact our support.",
      });
    })
  }

    useEffect(() => {
        if (timeLeft <= (20*60*1000)) {
          setButtonDisabled(false);
        } else {
          const timer = setInterval(() => {
            if(timeLeft > (20*60*1000)) 
              setTimeLeft((prev) => Math.max(prev - 1000, 0));
          },1000);    
          return () => clearInterval(timer);
        }    
    }, [timeLeft]);

    async function saveInterview() {
      try {
        const response = await fetch("/api/saveQuestionAnswer", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ 
            candidate_id : candidateId, 
            Answers: messages
          }),
        });
    
        if (!response.ok) {
          toast({
            variant: "destructive",
            title: "Error",
            description: "Failed to save the interview details. Proceed to coding section, and afterwards contact our suport team.",
          });
        }
    
        const data = await response.json();
        toast({
          title: "Data Saved",
          description: "Interview Details saved. Proceed to coding section.",
        });
      } catch (error) {
        toast({
          variant: "destructive",
          title: "Error",
          description: "Internal Server Error.",
        });
      }
    }
    

    const GoToCode = async () => {
      if (stream !== undefined) {
        await avatar.current?.closeVoiceChat();
        await endSession();
      }
      await saveInterview();
      router.push('/Interview/Coding');
    }

    const handleStartInterview = async () => {
      setModalVisible(false);
      await startSession();
      await handleSpeak(initialText);
      setMessages((prevMessages) => [
        ...prevMessages,
        { id: prevMessages.length + 1, text: initialText, isUser: false },
      ]);      
    };
  
    const handleSubmit = async () => {
      if(questionCount < 15) {
        await fetch("/QuestionGenerate", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ value: messages }),
        })
          .then((res) => res.json())
          .then((res) => {
            if(res.nextQuestion && res.nextQuestion.toLowerCase().includes("interview is terminated") && res.nextQuestion.toLowerCase().includes("vague answers")) {
              toast({
                variant: "destructive",
                title: "Interview Termination",
                description: "The interview is terminated due to vague answers. You are being proceeded to code section in few seconds.",
              });
            }
            handleSpeak(res.nextQuestion);
            setQuestionCount(questionCount + 1);
            setInputText(res.nextQuestion);
          })
          .catch((err) => {
            toast({
              variant: "destructive",
              title: "Error",
              description: "There's some issue on our server! Please try starting interview again. If issue persists contact our support.",
            });
          })
      } else { 
        toast({
          title: "Interview Complete",
          description: "That's it for now. Your interview is completed and you will be proceeded for the coding assessment now.",
        });
        () => GoToCode();
      }      
    };
  
    useEffect(() => {
      if(isLoadingRepeat === false) {
        if (inputText && messages[messages.length - 1].text !== inputText) {
          setMessages((prevMessages) => [
            ...prevMessages,
            { id: prevMessages.length + 1, text: inputText, isUser: false },
          ]);
        }
      }
    }, [inputText,isLoadingRepeat]);
  
    const userResponse = async () => {
      if (transcript.length > 0) {
        stopListeningToUser();
        setMessages((prevMessages) => [
          ...prevMessages,
          { id: prevMessages.length + 1, text: transcript, isUser: true },
        ]);
        setIsMessageFlag((prev)=>prev+1);
      }
      setTranscript("");
    }; 

    useEffect(() => {
      isMessageFlag !== 0 ? 
        handleSubmit(): "";
    }, [isMessageFlag,setIsMessageFlag])

    useEffect(() => {
        const SpeechRecognition =
          window.SpeechRecognition || window.webkitSpeechRecognition;
      
        if (SpeechRecognition) {
          const recognition = new SpeechRecognition();
          recognition.lang = "en-US";
          recognition.interimResults = true;
          recognition.continuous = true;
      
          recognition.onresult = (event) => {
            let interimTranscript = '';
            for (let i = event.resultIndex; i < event.results.length; i++) {
              const result = event.results[i];
              if (result.isFinal) {
                setTranscript((prev) => prev + result[0].transcript + ' ');
              } else {
                interimTranscript += result[0].transcript;
              }
            }
          };
      
          recognition.onerror = (event : any) => {
            toast({
              variant: "destructive",
              title: "Error",
              description: "There's some issue with audio recognition, please try again and if issue persists, contact our support.",
            });
          };

          recognition.onend = () => {
            setIsListening(false);
          };
      
          recognitionRef.current = recognition; // Store the instance
        } else {
          console.warn("SpeechRecognition API is not supported in this browser.");
        }
      
        return () => {
          if (recognitionRef.current) {
            recognitionRef.current.abort();
            recognitionRef.current = null;
          }
        };
      }, []);

    const startListeningToUser = () => {
      if (recognitionRef.current && !isListening) {
        setIsListening(true);
        recognitionRef.current.start();
      }
    };
  
    const stopListeningToUser = () => {
      if (recognitionRef.current && isListening) {
        setIsListening(false);
        recognitionRef.current.stop();
      }
    };
  
    useEffect(() => {
      const textarea = textareaRef.current;
      if (textarea) {
        // textarea.style.height = "auto";
        textarea.style.height = `${textarea.scrollHeight}px`;
      }
    }, [transcript]);
  
    async function fetchAccessToken(): Promise<string> {
      try {
        const response = await fetch("/api/GetAccessToken", {
          method: "POST",
        });
        const token = await response.text();
        return token;
      } catch (error) {
      }
      return "";
    }
  
    async function startSession() {
      setIsLoadingSession(true);
      const newToken = await fetchAccessToken();
  
      avatar.current = new StreamingAvatar({
        token: newToken,
      });
  
      avatar.current.on(StreamingEvents.STREAM_DISCONNECTED, () => {
      });
  
      avatar.current.on(StreamingEvents.AVATAR_STOP_TALKING, (e : any) => {
        startListeningToUser();
      });
  
      avatar.current?.on(StreamingEvents.STREAM_READY, (event : any) => {
        setStream(event.detail);
      });
  
      try {
        const res = await avatar.current.createStartAvatar({
          quality: AvatarQuality.Medium,
          avatarName: "June_HR_public",
          // avatarName: avatarName?avatarName:"josh_lite3_20230714",
          voice: { 
            rate: 1.0,
            emotion: VoiceEmotion.EXCITED,
          },
          language: "en",
          disableIdleTimeout: true,                                               //To disable Timeout of avatar which is 2 minutes by default
        });
  
        setData(res);
  
      } catch (error) {
        toast({
          variant: "destructive",
          title: "Error",
          description: "There's some issue with Video feed, please proceed with chat mode.",
        });
      } finally {
        setIsLoadingSession(false);
      }
    }
  
    async function handleSpeak(inputText : string) {
      setIsLoadingRepeat(true);
      if (!avatar.current) {
        setDebug("Avatar API not initialized");
        return;
      }
  
      await avatar.current
        .speak({
          text: inputText,
          taskType: TaskType.REPEAT,
          taskMode: TaskMode.SYNC,
        })
        .catch((e : any) => {
          setDebug(e.message);
        });
      setIsLoadingRepeat(false);
    }
  
    async function endSession() {
      await avatar.current?.stopAvatar();
      setStream(undefined);
    }
  
    useEffect(() => {
      if (stream && mediaStream.current) {
        mediaStream.current.srcObject = stream;
        mediaStream.current.onloadedmetadata = () => {
          mediaStream.current?.play();
          setDebug("Playing");
        };
      }
    }, [mediaStream, stream]);
    
  return (
    <>
    {isLoading || isLoadingSession ? 
      <Image src={Loader} alt="loader" height={70} width={70} className="absolute top-[50%] left-[50%]"/>
    : 
    
    <div className="min-h-screen bg-white mb-4">

      {isModalVisible && (
        <div className="fixed inset-0 flex items-center justify-center bg-black bg-opacity-50 z-10">
          <div className="bg-white p-6 rounded-lg shadow-lg text-center">
            <h2 className="text-xl font-bold text-gray-800 mb-4">
              Welcome to the Interview
            </h2>
            <p className="text-sm text-gray-600 mb-6">
              Please click the button below to start your interview.
            </p>
            <Button
              className="mt-4"
              onClick={handleStartInterview}
            >
              Start Interview
            </Button>
          </div>
        </div>
      )}
          
      <div className="flex justify-between mx-auto space-y-8 px-10">
        <h2 className="text-2xl font-bold text-center text-gray-900 pt-4">
          L1 Interview
        </h2>
        <Button
          onClick={() => GoToCode()}
          disabled = {isButtonDisabled}
        >
          Code Section
        </Button>
      </div>

      <div className="max-w-6xl mx-auto mt-10 flex flex-row">
        <div className="w-full ">
        <Card className="overflow-hidden border border-black">
          <CardContent className="p-6">
          {stream ? (
            <div className="h-[500px] justify-center items-center flex rounded-lg overflow-hidden">
              <video
                ref={mediaStream}
                autoPlay
                playsInline
                style={{
                  width: "100%",
                  height: "100%",
                  objectFit: "contain",
                }}
              >
                <track kind="captions" />
              </video>
            </div>
          ) : (
              <div className="w-full aspect-video bg-gray-200 rounded-lg flex items-center justify-center text-gray-400">
                Be ready! Your Interview will start soon.
              </div>
            )}
          </CardContent>
        </Card>
        </div>
        <div className="w-full px-5">
          <div className="p-4 bg-white rounded-lg shadow-lg overflow-hidden flex flex-col border border-gray-300 h-[75vh]">
            <h2 className="text-2xl font-bold mb-2">Questions</h2>
            <hr/>
            <div className="flex-grow overflow-y-auto mb-4 mt-4 **scrollbar-thumb-gray-400 scrollbar-track-gray-200 scrollbar-thin">
              {messages.map((message) => (
                <div 
                  key={message.id} 
                  className={`mb-4 p-3 rounded-lg ${
                    message.isUser ? 'bg-blue-100 ml-auto' : 'bg-gray-100'
                  } max-w-[80%]`}
                >
                  <p className={`text-sm ${message.isUser ? 'text-blue-800' : 'text-gray-800'}`}>
                    {message.text}
                  </p>
                </div>
              ))}
            </div>
            <div className="mt-auto flex">
              <textarea
                // disabled
                ref={textareaRef}
                placeholder="Your response will appear here..."
                className="w-full p-2 border border-gray-300 rounded-lg resize-none"
                value={transcript}
                onChange={(e) => setTranscript(e.target.value)}
              />
              <Button 
                className="p-2 bg-white hover:bg-white"
                onClick={() => userResponse()} 
              >
                <FaTelegramPlane className="fill-primary" />
              </Button>
            </div>
          </div>
        </div>      
      </div>
    </div>
    }
    </>

    
  )
}