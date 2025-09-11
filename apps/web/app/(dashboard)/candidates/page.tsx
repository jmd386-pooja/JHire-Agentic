"use client";

import ResumeForm from "@/components/layout/ResumeForm";
import CandidatesTable from "@/components/layout/CandidatesTable";
import Image from "next/image";
import JmanLogo from "@/images/JMANLogoBlue.png";

export default function CandidatesPage() {
  return (
    <div className="flex flex-col">
      <div className="space-y-6 p-8 pt-3 relative max-w-7xl mx-auto w-full">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-3xl font-bold px-4 pt-4">Candidates</h2>
          <div style={{ position: "sticky" }}>
            <ResumeForm />
          </div>
        </div>

        <div>
          <CandidatesTable />
        </div>
      </div>

      <footer className="w-full bg-gray-200 py-2 px-2">
        <div className="max-w-7xl mx-auto flex justify-between items-center">
          <p className="text-sm text-gray-600 m-0">
            © 2024 JMAN, All Rights Reserved
          </p>
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
