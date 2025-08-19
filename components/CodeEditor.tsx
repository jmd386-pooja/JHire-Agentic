"use client"

import Editor from "@monaco-editor/react"
import React, { useEffect, useState } from "react"
import axios from "axios"
import Select from "react-select"
import useKeyPress from "@/hooks/use-key-press"
import {languageOptions} from "@/components/languageOptions"
import { useToast } from "@/hooks/use-toast"
import { useRouter } from "next/navigation"
import Loader from '@/images/CandidateLoader.gif'
import Image from "next/image"

interface LanguageOption {
  id: number;
  label: string;
  value: string;
}

interface OutputDetail {
  stdout?: string;
  stderr?: string;
  compile_output?: string;
  status?: {
    id: number;
    description: string;
  };
  time?: string;
  memory?: string;
}

interface Output {
  input: string;
  expected_output : string;
  your_output : string;
  result : string;
  outputDetail : OutputDetail;
}

interface Question {
  id: string;
  question: string;
  testcases: Array<{
    input: string,
    output: string
}>;
}

const DefaultCode = `/**
* Your code goes here
*/

`;

const CodingEditor: React.FC = () => {
  const [code, setCode] = useState<string>(DefaultCode);
  const [outputDetails, setOutputDetails] = useState<Output[] | null>([]);
  const [processing, setProcessing] = useState<boolean>(false);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [candidateId, setCandidateId] = useState<number>();
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const theme = { value: "cobalt", label: "Cobalt" };
  const [language, setLanguage] = useState<LanguageOption>(languageOptions[0] || { id: 1, label: "JavaScript", value: "javascript" });
  const [questionList, setQuestionList] = useState<Question[]>([]);
  const [detailsVisible, setDetailsVisible] = useState(false);
  const router=useRouter();
  const toggleDetails = () => {
    setDetailsVisible((prev) => !prev);
  };

  useEffect(() => {
    const fetchCookies = async () => {
      try {
        const response = await fetch("/api/getCookies");
        const data = await response.json();
        setCandidateId(data.candidateId);
        getQuestion(data.candidateId)
      } catch (error) {
      }
    };

    fetchCookies();
  }, []);

    async function getQuestion(candidateID : number): Promise<string> {
      try {
        const response = await fetch("/api/getQuestion", {
          method: "POST",
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ 
            candidate_id: candidateID
          }),
        });
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        const result = await response.json();
  
        if (result.success) {
          //
        } else {
          toast({
            variant: "destructive",
            title: "Error",
            description: "There's some issue with our server, reload after some time, if this issue persists contact our support",
          });
        }
        result ? 
        setQuestionList((questions) => [
          ...questions,
          result.data
        ]) : "";
      } catch (error) {
        toast({
          variant: "destructive",
          title: "Error",
          description: "There's some issue with our server, reload after some time, if this issue persists contact our support",
        });
      }
      setIsLoading(false);
      return "";
    }
  

  const enterPress = useKeyPress("Enter");
  const ctrlPress = useKeyPress("Control");
  const { toast } = useToast();

  const onSelectChange = (selectedLanguage: LanguageOption) => {
    setLanguage(selectedLanguage);
  };

  const handleSelectChange = (selectedOption: LanguageOption | null) => {
    if (selectedOption) {
      onSelectChange(selectedOption);
    }
  };

  useEffect(() => {
    if (enterPress && ctrlPress) {
      handleCompile(questionList[0]);
    }
  }, [ctrlPress, enterPress]);

  const onChange = (action: string, data: string) => {
    if (action === "code") {
      setCode(data);
    } else {
      console.warn("Unhandled action:", action);
    }
  };

  const handleCompile = (question: Question) => {
    setProcessing(true);
    setOutputDetails(null);
  
    // const results: Array<{ input: string; output: string; result: string }> = [];
  
    const runTestCase = async (testcase: { input: string; output: string }) => {
      const formData = {
        language_id: language.id,
        source_code: btoa(code),
        stdin: btoa(testcase.input),
      };
  
      const options = {
        method: "POST",
        url: process.env.NEXT_PUBLIC_RAPID_API_URL,
        params: { 
          base64_encoded: "true", 
          fields: "*" 
        },
        headers: {
          "content-type": "application/json",
          "Content-Type": "application/json",
          "X-RapidAPI-Key": process.env.NEXT_PUBLIC_RAPID_API_KEY || "",
          "X-RapidAPI-Host": process.env.NEXT_PUBLIC_RAPID_API_HOST || "",
        },
        data: formData,
      };
  
      try {
        // Submit the code
        const response = await axios.request(options);
        const token = response.data.token;
  
        // Check the status until complete
        const output : any = await checkStatus(token);
  
        // Decode the output
        const decodedOutput = atob(output.stdout || "");
        
        // Compare the output with the expected result
        const isCorrect = decodedOutput.trim() === testcase.output.trim();

        const results = ({
          input: testcase.input,
          expected_output: testcase.output,
          your_output : decodedOutput,
          result: isCorrect ? "Passed" : `Failed (Got: ${decodedOutput})`,
          outputDetail : output
        });

        setOutputDetails((prevOutputDetails) => {
          // Check for null and initialize with an empty array if necessary
          const updatedDetails = prevOutputDetails ? [...prevOutputDetails, results] : [results];
          return updatedDetails;
        });
      } catch (err : any) {
        const error = err.response ? err.response.data : err;
        const results = ({
          input: testcase.input,
          expected_output: testcase.output,
          result: "Error",
        });
  
        if (err.response?.status === 429) {
          toast({
            variant: "destructive",
            title: "Error",
            description: "We are having issues processing your code, contact our support team",
          });
        } else {
          toast({
            variant: "destructive",
            title: "Error",
            description: "We are having issues processing your code. Please try again",
          });
        }
      }
    };
  
    const runAllTestCases = async () => {
      for (const testcase of question.testcases) {
        await runTestCase(testcase);
      }
  
      setProcessing(false);
    };
  
    runAllTestCases();
  };
  
  const checkStatus = async (token: string) => {
    const options = {
      method: "GET",
      url: `${process.env.NEXT_PUBLIC_RAPID_API_URL}/${token}`,
      params: { base64_encoded: "true", fields: "*" },
      headers: {
        "X-RapidAPI-Host": process.env.NEXT_PUBLIC_RAPID_API_HOST || "",
        "X-RapidAPI-Key": process.env.NEXT_PUBLIC_RAPID_API_KEY || "",
      },
    };
  
    return new Promise((resolve, reject) => {
      const pollStatus = async () => {
        try {
          const response = await axios.request(options);
          const statusId = response.data.status?.id;
  
          if (statusId === 1 || statusId === 2) {
            // Still processing, poll again after 2 seconds
            setTimeout(pollStatus, 3000);
          } else if (statusId === 3) {
            // Completed successfully
            resolve(response.data);
          } else {
            // Failed or error
            reject(new Error("Failed to compile or run code"));
          }
        } catch (err) {
          reject(err);
        }
      };
  
      pollStatus();
    });
  };

  const handleSubmit = async (questionId:string) => {
    setSubmitting(true);
    try {
      const res = await fetch("/api/EvaluateCode", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          candidateId: candidateId,
          questionId: questionId,
          code: code,
          language: language,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        toast({
          title: "Success",
          description: "Successfully Submitted for Evaluation.",
        });
        // Navigate to the new page after success
        router.push("/Interview/Feedback");
      } else {
        throw new Error("Server error");
      }
    } catch (err) {
      toast({
        variant: "destructive",
        title: "Error",
        description:
          "There's some issue on our server! Please try again. If issue persists contact our support.",
      });
    } finally {
      setSubmitting(false);
    }
  };

  const showSuccessToast = (msg?: string) => {
    toast({
      title: "Success",
      description: msg || `Compiled Successfully!`,
    });
  };

  const showErrorToast = (msg?: string, timer?: number) => {
    toast({
      variant: "destructive",
      title: "Error",
      description: msg || `Something went wrong! Please try again.`
    });
  };

  return (
    <>
    {isLoading ? 
      <Image src={Loader} alt="loader" height={70} width={70} className="absolute top-[50%] left-[50%]"/>
    :  
    <>
      {/* <div className="h-4 w-full bg-gradient-to-r from-pink-500 via-red-500 to-yellow-500"></div> */}
      <div className="flex flex-row w-full h-85vh px-10 mt-5">
        <div className="w-1/3 p-4 border-r bg-white">
          <h2 className="text-xl font-bold mb-4">Question</h2>
          <pre className="whitespace-pre-wrap mb-8">{questionList[0].question}</pre>
          <ul className="w-1/3">
              {questionList[0].testcases.map((testCase, index) => (
                <li key={index} className="p-2 rounded">
                  <strong><pre>Example {index+1}</pre></strong>
                  <br />
                  <strong><pre className="whitespace-pre-wrap">Input:</pre></strong><pre> {testCase.input}</pre>
                  <br />
                  <strong><pre>Output:</pre></strong><pre> {testCase.output}</pre>
                </li>
              ))}
          </ul>
        </div>    
      
      <div className="w-2/3">
        <div className="flex flex-row space-x-4 px-4 py-4">
          <div className="px-4 py-2">
            <div className="dropdown-container mt-4 w-[200px]" suppressHydrationWarning>
              <Select
                id="filter-by-category"
                instanceId="filter-by-category"
                inputValue=""
                placeholder={`Filter By Category`}
                options={languageOptions}
                defaultValue={languageOptions[0]}
                onChange={(selectedOption) => handleSelectChange(selectedOption)}
              />
            </div>
          </div>
        </div>
        <div className="flex flex-col space-x-4 items-start px-4 py-4">
          <div className="w-full items-end">
            <div className="rounded-md overflow-hidden border: 1px border-solid border-black h-75vh">
              <Editor
                height="45vh"
                width={`100%`}
                language={language.value || "javascript"}
                value={code}
                // theme={theme.value}
                theme={"cobalt"}
                defaultValue="// some comment"
                onChange={(value: string | undefined) => onChange("code", value ?? "")}
              />
            </div>
          </div>
          <div className="flex flex-row align-center justify-end w-full gap-8 pr-10">
            <button
                onClick={() => handleCompile(questionList[0])}
                disabled={processing}
                // className="mt-4 border-2 px-4 py-2 rounded-md  bg-black text-white"
                className={
                  `mt-4 border-2 border-black px-4 py-2 rounded-md  bg-black text-white
                  ${processing ? "opacity-50" : "hover:bg-white hover:text-black"}`
                }
              >
                {processing ? "Processing..." : "Compile and Execute"}
            </button>
            <button
                onClick={() => handleSubmit(questionList[0].id)}
                disabled={submitting}
                className={
                  `mt-4 border-2 border-black px-4 py-2 rounded-md  bg-black text-white
                  ${submitting ? "opacity-50" : "hover:bg-white hover:text-black"}`
                }
              >
                {/* Submit */}
                {submitting ? "Submitting..." : "Submit"}
            </button>
          </div>
          <div className="flex flex-shrink-0 w-[30%] flex-col">
            <div>
              <h1 className="font-bold text-xl bg-clip-text text-transparent bg-gradient-to-r from-slate-900 to-slate-700 mb-2">
                Output
              </h1>
              <div className="w-full p-4 space-y-4 bg-gray-50 rounded-lg shadow">
      {outputDetails?.map((detail, index) => (
        <div
          key={index}
          className="border-b border-gray-300 pb-4 mb-4 last:border-b-0 last:pb-0 last:mb-0"
        >
          <h2 className="font-bold text-lg mb-2">Case {index + 1}</h2>
          <div className="space-y-2">
            <p>
              <span className="font-semibold">Input: </span>
              <code>{detail.input}</code>
            </p>
            <p>
              <span className="font-semibold">Expected Output: </span>
              <code>{detail.expected_output}</code>
            </p>
            <p>
              <span className="font-semibold">Your Output: </span>
              <code
                className={
                  detail.result === "pass" ? "text-green-500" : "text-red-500"
                }
              >
                {detail.your_output}
              </code>
            </p>
            <button
              onClick={toggleDetails}
              className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 transition"
            >
              {detailsVisible ? "Hide Details" : "Show Details"}
            </button>
          </div>
          {detailsVisible && (
            <div className="mt-4 bg-gray-100 p-3 rounded">
              <p>
                <span className="font-semibold">Memory: </span>
                {detail.outputDetail.memory}
              </p>
              <p>
                <span className="font-semibold">Time: </span>
                {detail.outputDetail.time}
              </p>
              {detail.outputDetail.stderr && (
                <pre className="mt-2 text-red-500">
                  <span className="font-semibold">Error: </span>
                  {atob(detail.outputDetail.stderr)}
                </pre>
              )}
              {detail.outputDetail.stdout && (
                <pre className="mt-2 text-green-500">
                  <span className="font-semibold">Output: </span>
                  {atob(detail.outputDetail.stdout)}
                </pre>
              )}
            </div>
          )}
        </div>
      ))}
    </div>

            </div>
            {/* {outputDetails && 
              <div className="metrics-container mt-4 flex flex-col space-y-3">
                <p className="text-sm">
                  Memory:{" "}
                  <span className="font-semibold px-2 py-1 rounded-md bg-gray-100">
                    {outputDetails[0]?.outputDetail.memory}
                  </span>
                </p>
                <p className="text-sm">
                  Time:{" "}
                  <span className="font-semibold px-2 py-1 rounded-md bg-gray-100">
                    {outputDetails[0]?.outputDetail.time}
                  </span>
                </p>
              </div>
            } */}

          </div>
        </div>
        </div>
      </div> 
      </>
    }
    </>
  );
};

export default CodingEditor;
