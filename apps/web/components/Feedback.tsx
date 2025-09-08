"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import bgImage from "@/images/JMANLogoBlue.png"
import Image from "next/image"
import { Textarea } from "@/components/ui/textarea"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { StarRating } from "./StarRating"
import { useToast } from "@/hooks/use-toast";

interface Feedback {
    ui: number;
    questionLevel: number;
    feasibility: number;
    overall: string;
}
  

export function FeedbackPage() {
  const [rating, setRating] = useState<number>(0)
  const [showDialog, setShowDialog] = useState<boolean>(false)
  const [candidateId, setCandidateId] = useState<number | null>(null)
  const [feedback, setFeedback] = useState<Feedback>({
    ui: 0,
    questionLevel: 0,
    feasibility: 0,
    overall: "",
  })
  const { toast } = useToast();
  useEffect(() => {
    const fetchCookies = async () => {
      try {
        const response = await fetch("/api/getCookies");
        const data = await response.json();
        setCandidateId(data.candidateId);
        console.log("Candidate ID:", data.candidateId);
      } catch (error) {
      }
    };

    fetchCookies();
  }, []);

  const handleSubmit = async (e : any) => {
    e.preventDefault()
    if(!candidateId || ! feedback || !rating){
      toast({
        variant: "destructive",
        title: "Error submitting feedback",
        description: "Fill all the fields.",
      });
    } else {
    await fetch("/api/submitFeedback",{
      method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ 
          candidate_id : candidateId,
          feedback_text : feedback,
          ratings : rating,
        }),
      })
      .then((res) => res.json())
        .then((res) => {
          console.log("res.status : ", res)
          if(res.status === 300) {
            toast({
              variant: "destructive",
              title: "Feedback already submitted.",
            });
          } else {
          toast({
            title: "Success",
            description: "Feedback submitted successfully.",
          });
        }
        })
      .catch((err) => {                         
        toast({
          variant: "destructive",
          title: "Error submitting feedback",
        });
      })
    setShowDialog(true)
    }
  }

  const handleInputChange = (value : number | string, name : string) => {
    setFeedback(prev => ({ ...prev, [name]: value }))
  }

  return (
    <div>
      <div>
      <Image src={bgImage} alt="bg-img" className="w-40 h-14 px-2"/>
      </div>
    <div className="min-h-screen bg-white bg-cover bg-center flex flex-col items-center justify-center p-4 -mt-12">

      <Card className="w-full max-w-2xl">
        <CardHeader >
          <CardTitle className="text-2xl font-bold text-primary text-center">Interview Feedback</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-8">
          <div className="space-y-3 text-center">
              <Label>How would you rate the user interface of the interview platform?</Label>
              <div className="flex align-center justify-center">
                <StarRating 
                  rating={feedback.ui} 
                  onRatingChange={(value) => handleInputChange(value,"ui")} 
                />
              </div>
            </div>

            <div className="space-y-3 text-center">
              <Label>How appropriate was the level of questions?</Label>
              <div className="flex align-center justify-center">
                <StarRating 
                  rating={feedback.questionLevel} 
                  onRatingChange={(value) => handleInputChange(value, "questionLevel")} 
                />
              </div>
            </div>

            <div className="space-y-3 text-center">
              <Label>How feasible did you find the interview process?</Label>
              <div className="flex align-center justify-center">
                <StarRating 
                  rating={feedback.feasibility} 
                  onRatingChange={(value) => handleInputChange(value, "feasibility")} 
                />
              </div>
            </div>

            <div className="space-y-3 text-center">
              <Label htmlFor="overall">Please provide any additional feedback or suggestions:</Label>
              <Textarea
                id="overall"
                name="overall"
                value={feedback.overall}
                onChange={(e) => {
                  if (e.target.value.length <= 200) {
                    handleInputChange(e.target.value, "overall");
                  }
                }}
                placeholder="Your overall experience and suggestions..."
                rows={4}
                className="px-5"
                maxLength={200} 
              />
              <p className="text-sm text-gray-500 text-right">
                {feedback.overall.length}/200 characters
              </p>
            </div>
            <div className="space-y-3 text-center">
              <Label>Overall Rating:</Label>
              <div className="flex align-center justify-center">
                <StarRating rating={rating} onRatingChange={setRating} />
              </div>
            </div>
          </form>
        </CardContent>
        <CardFooter>
          <Button onClick={handleSubmit} className="w-full bg-primary  text-white">
            Submit Feedback
          </Button>
        </CardFooter>
      </Card>

      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Thank You for Your Feedback</DialogTitle>
            <DialogDescription>
              We appreciate your input. It helps us improve our interview process.
              You may now close this window.
            </DialogDescription>
          </DialogHeader>
        </DialogContent>
      </Dialog>



    </div>
    </div>
  )
}

