import { useState, useEffect } from "react"
import { useToast } from "@/hooks/use-toast"
import { useRouter } from "next/navigation"
import { usePathname } from 'next/navigation'
import Image from "next/image"
import Logo from "@/images/JMANfooter1.png"

interface HeaderProps {
    username: string;
    onExit: () => void;
  }
  
export function Header({ username, onExit }: HeaderProps) {
  const pathname = usePathname();
  const [loading, setLoading] = useState<boolean>(true);
  const [startTime, setStartTime] = useState<number | null>(null);
  const [timeLeft, setTimeLeft] = useState<number>(30 * 60 * 1000);
  const { toast } = useToast();
  const router = useRouter();

  const [candidateId, setCandidateId] = useState<number | null>(null);

  useEffect(() => {
    const fetchCookies = async () => {
      try {
        const response = await fetch("/api/getCookies");
        const data = await response.json();
        setCandidateId(data.candidateId);
      } catch (error) {
      }
    };

    fetchCookies();
  }, []);

  useEffect(() => {
    setLoading(true);
    async function getStartTime() {
      await fetch("/api/getInitialTime",{
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ 
          candidate_id: candidateId
        }),
      })
      .then((res) => res.json())
      .then((res) => {
        const fetchedTime = new Date(res.startTime).getTime();
        setStartTime(fetchedTime);

        const now = Date.now();
        const elapsed = now - fetchedTime;
        const initialRemaining = Math.max(30 * 60 * 1000 - elapsed, 0);
        // setTimeLeft(initialRemaining);
      })
      .catch((err) => {
        toast({
          variant: "destructive",
          title: "Server Error",
          description: "There's some issue on our server! Please try starting interview again. If issue persists contact our support.",
        });
      })
    }
    if(candidateId && pathname !== '/instructions' && pathname !== '/Instructions') 
      getStartTime();
    setLoading(false);
  },[candidateId, setCandidateId, pathname]);

  useEffect(() => {
    if(pathname !== '/instructions' && pathname !== '/Instructions') {
      if (timeLeft > 0) {
        const timer = setInterval(() => {
          setTimeLeft((prev) => Math.max(prev - 1000, 0));
        }, 1000);

        return () => clearInterval(timer); 
      } else {
        handleTimeUp();
      }
    }
  }, [timeLeft,pathname]);

  const exitPage = () => {
    router.push('/Interview/Feedback');
  }

  const handleTimeUp = () => {
    toast({
      variant: "destructive",
      title: "Time's Up",
      description: "Time to give test ended! Exiting test.",
    });
    exitPage();
  };

  const formatTime = (ms: number) => {
    const minutes = Math.floor(ms / (60 * 1000));
    const seconds = Math.floor((ms % (60 * 1000)) / 1000);
    return `${minutes}:${seconds < 10 ? `0${seconds}` : seconds}`;
  };

  return (
    <header className="flex justify-between items-center p-4 bg-gradient-to-r from-[#341ba5] via-[#60adce] to-[#71e6e0] text-white">
      {loading === false &&
      <div className="flex flex-row justify-between align-center w-full">
        <div className="flex flex-row gap-x-5">
          <Image src={Logo} alt="Company Logo" width={100} height={15}/>
          <h1 className="text-xl py-2">{username}</h1>          
        </div>
        
      
        <div className="flex items-center space-x-4">
          <span className="text-lg font-semibold -ml-10">{formatTime(timeLeft)}</span>
        </div>
      
      <button
        onClick={onExit}
        className="bg-red-600 text-white px-4 py-2 rounded hover:bg-red-700"
      >
        Exit Interview
      </button>
      </div>
      }
    </header>
  );
}
