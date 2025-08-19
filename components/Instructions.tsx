"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { Checkbox } from "@/components/ui/checkbox"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import {Header} from '@/components/Header'

export function InstructionsPage() {
  const [accepted, setAccepted] = useState<boolean>(false)
  const [isPopupVisible, setPopupVisible] = useState<boolean>(false)
  const [username, setUsername] = useState<string>("User");
  const router = useRouter()

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

  const handleStartTest = () => {
    if (accepted) {
      router.push("/Interview")
    }
  }

  const handleExit = () => {
    setPopupVisible(true);
  }

  //handle cancel on popup when exit
  const handleCancel = () => {
    setPopupVisible(false);                
  };

  //confirm exit
  const handleConfirm = async () => {
    setPopupVisible(false);
    await fetch("/api/auth/logout",{
      method: "POST"
    })
    .catch((err) => {
    })  
    router.push('/Interview/Feedback');
  };

  return (
    <div className="min-h-screen flex flex-col bg-white">
      <Header username={username} onExit={handleExit} />

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
      
        <h1 className="text-2xl font-bold text-center py-8">Interview Instructions</h1>

      <main className="flex-grow overflow-auto p-6">
        <Card className="max-w-4xl mx-auto">
          <CardContent className="space-y-8 mt-5">
            <section>
              <h2 className="text-xl font-semibold text-primary mb-4">Before You Begin</h2>
              <p className="mb-4">Please read the following instructions carefully:</p>
              <ol className="list-decimal list-inside space-y-2">
                <li>Ensure you have a stable internet connection.</li>
                <li>Find a quiet place where you wont be disturbed.</li>
                <li>Make sure your camera and microphone are working properly.</li>
                <li>You will have 30 minutes to complete the interview.</li>
                <li>Answer all questions to the best of your ability.</li>
                <li>If you encounter any technical issues, please contact our support team.</li>
              </ol>
            </section>

            <section>
              <h2 className="text-xl font-semibold text-primary mb-4">Interview Process</h2>
              <p className="mb-4">The interview will consist of the following stages:</p>
              <ol className="list-decimal list-inside space-y-2">
                <li>A series of multiple-choice questions to assess your theoretical knowledge.</li>
                <li>Coding challenges to evaluate your practical skills.</li>
                <li>A brief video response section for behavioral questions.</li>
              </ol>
            </section>

            <section>
              <h2 className="text-xl font-semibold text-primary mb-4">Terms and Conditions</h2>
              <p className="mb-4">By accepting these terms, you agree to:</p>
              <ul className="list-disc list-inside space-y-2">
                <li>Not share any information about the interview questions with others.</li>
                <li>Complete the interview without any external help or resources unless explicitly allowed.</li>
                <li>Allow us to record the interview session for review purposes.</li>
                <li>Understand that any form of cheating will result in immediate disqualification.</li>
              </ul>
            </section>
          </CardContent>
          <CardFooter className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center space-x-2">
              <Checkbox 
                id="terms" 
                checked={accepted}
                onCheckedChange={(checked : boolean) => setAccepted(checked)}
              />
              <label
                htmlFor="terms"
                className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
              >
                I have read and accept the terms and conditions
              </label>
            </div>
            <Button 
              onClick={handleStartTest} 
              disabled={!accepted}
              className="w-full sm:w-auto bg-primary hover:bg-purple-700 text-white"
            >
              Start Test
            </Button>
          </CardFooter>
        </Card>
      </main>
    </div>
  )
}

