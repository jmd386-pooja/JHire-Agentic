"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Mail, FileSpreadsheet } from "lucide-react";
import ResumeForm from "@/components/layout/ResumeForm";
import { useToast } from "@/hooks/use-toast";
import CandidatesTable from "@/components/layout/CandidatesTable";
import Image from "next/image";
import JmanLogo from "@/images/JMANLogoBlue.png"



interface Candidate {
  id: string;
  name: string;
  email: string;
  resumeUrl: string;
  status: string;
}


export default function CandidatesPage() {
  console.log("HIiiii");
  
  return (
    <div className="min-h-screen flex flex-col">
      {/* Main Content */}
      <div className="flex-1 space-y-6 overflow-y-auto p-8 pt-3 relative max-w-7xl mx-auto w-full">
        {/* Header Row */}
        <div className="flex justify-between items-center mb-6">
          {/* Candidates Title */}
          <h2 className="text-3xl font-bold px-4 pt-4">Candidates</h2>
          {/* ResumeForm Component */}
          <div style={{ position: "sticky" }}>
            <ResumeForm />
          </div>
        </div>
  
        {/* Candidates Table */}
        <div>
          <CandidatesTable />
        </div>
      </div>
  
      {/* Footer */}
      <footer className="w-full bg-gray-200 py-2 px-2">
        <div className="max-w-7xl mx-auto flex justify-between items-center">
          <p className="text-sm text-gray-600 m-0">© 2024 JMAN, All Rights Reserved</p>
          <Image
            src={JmanLogo}
            alt="JMAN Logo"
            width={120}
            height={40}
            className="m-0"
          />
        </div>
      </footer>
    </div>
  );
  
}