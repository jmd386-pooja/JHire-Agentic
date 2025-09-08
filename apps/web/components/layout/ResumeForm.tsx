'use client';

import React, { useState, useRef } from 'react';
import { Modal } from '@/components/ui/modal'; // Ensure you have a Modal component implemented
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useToast } from '@/hooks/use-toast';
import { UploadCloud, XCircle } from 'lucide-react';

const ResumeForm: React.FC = () => {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [collegeName, setCollegeName] = useState<string>('');
  const [examDateTime, setExamDateTime] = useState<string>(''); // Stores both date and time
  const [expiryDateTime, setExpiryDateTime] = useState<string>(''); // Stores expiry date and time
  const [loading, setLoading] = useState<boolean>(false);
  const [success, setSuccess] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const { toast } = useToast();
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (files) {
      setSelectedFiles((prevFiles) => [...prevFiles, ...Array.from(files)]);
    }
  };

  const handleFileRemove = (fileName: string) => {
    setSelectedFiles((prevFiles) =>
      prevFiles.filter((file) => file.name !== fileName)
    );
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();

    if (selectedFiles.length === 0) {
      setError('Please select at least one PDF file to upload.');
      return;
    }

    if (!collegeName || !examDateTime || !expiryDateTime) {
      setError('Please fill in all the fields.');
      return;
    }

    setLoading(true);
    setError(null);
    setSuccess(false);

    const formData = new FormData();
    selectedFiles.forEach((file) => {
      formData.append('files', file);
    });
    formData.append('college', collegeName);
    formData.append('exam_date', examDateTime); // Include exam date-time
    formData.append('expiry_date', expiryDateTime); // Include expiry date-time
    try {
      const response = await fetch('/api/extractResumeDetails', {
        method: 'POST',
        body: formData,
      });
      if (!response.ok) {
        const { error } = await response.json();
        setError(`API Error: ${error}`);
      } else {
        console.log(response)
        setSuccess(true);
        toast({
          title: 'Success',
          description: 'Resumes registered successfully!',
        });

        setTimeout(() => {
          setSuccess(false);
          setSelectedFiles([]);
          setCollegeName('');
          setExamDateTime('');
          setExpiryDateTime('');
          if (fileInputRef.current) {
            fileInputRef.current.value = '';
          }
          setIsModalOpen(false);
          window.location.reload();
        }, 2000);
      }
    } catch (err: any) {
      setError(`Fetch Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto py-7 space-y-6">
  <div className="flex flex-col lg:flex-row lg:justify-end items-center">
    <Button
      onClick={() => setIsModalOpen(true)}
      style={{ backgroundColor: '#19105B', color: 'white', marginRight: '10px' }}
      className="px-4 py-2 rounded flex items-center lg:relative lg:top-0 lg:right-4 lg:ml-auto"
    >
      &#43; Upload Resumes
    </Button>

    <Button
      onClick={() => {
        fetch('/api/fetchSharepointResumes')
      }}
      style={{ backgroundColor: '#19105B', color: 'white' }}
      className="px-4 py-2 ms-3 rounded flex items-center lg:relative lg:top-0 lg:right-4 lg:ml-auto"
    >
      &#43; Fetch Resumes from Share Point
    </Button>
  </div>

  <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)}>
    <div className="p-6">
      <h2 className="text-xl font-bold mb-4">Upload Resumes</h2>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium mb-2">Upload Files</label>
          <Input
            type="file"
            accept=".pdf"
            multiple
            onChange={handleFileChange}
            ref={fileInputRef}
            className="w-full"
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-2">College Name</label>
          <select
            id="college-dropdown"
            value={collegeName}
            onChange={(e) => setCollegeName(e.target.value)}
            className="w-full border rounded-md p-2"
          >
            <option value="">Select College</option>
            {['CIT', 'SVCE', 'GEU'].map((college) => (
              <option key={college} value={college}>
                {college}
              </option>
            ))}
          </select>
        </div>

        <div className="lg:flex lg:space-x-4">
          <div className="w-full lg:w-1/2">
            <label className="block text-sm font-medium mb-2">Interview Date</label>
            <Input
              type="datetime-local"
              value={examDateTime}
              onChange={(e) => setExamDateTime(e.target.value)}
              required
              className="w-full"
            />
          </div>
          <div className="w-full lg:w-1/2 mt-4 lg:mt-0">
            <label className="block text-sm font-medium mb-2">Expiry Date</label>
            <Input
              type="datetime-local"
              value={expiryDateTime}
              onChange={(e) => setExpiryDateTime(e.target.value)}
              required
              className="w-full"
            />
          </div>
        </div>
        {selectedFiles.length > 0 && (
          <div
            className="mt-4 bg-gray-100 p-2 rounded-lg"
            style={{ maxHeight: '100px', overflowY: 'auto' }} // Scrollable container
          >
            <ul>
              {selectedFiles.map((file) => (
                <li
                  key={file.name}
                  className="flex items-center justify-between p-2 border-b last:border-b-0"
                >
                  <span className="truncate">{file.name}</span>
                  <button
                    type="button"
                    onClick={() => handleFileRemove(file.name)}
                    className="text-red-600 hover:text-red-800"
                  >
                    <XCircle className="h-5 w-5" />
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
        <div className="flex flex-col lg:flex-row lg:justify-end lg:space-x-4">
          <Button
            type="button"
            onClick={() => setIsModalOpen(false)}
            className="bg-gray-400 text-white px-4 py-2 rounded-lg mb-4 lg:mb-0"
          >
            Cancel
          </Button>
          <Button
            type="submit"
            style={{ backgroundColor: '#19105B', color: 'white' }}
            disabled={loading}
            className={`px-6 py-2 rounded-lg ${
              loading ? 'bg-gray-400' : 'bg-blue-600 hover:bg-blue-700'
            } text-white`}
          >
            {loading ? 'Processing...' : 'Upload'}
          </Button>
        </div>
      </form>
    </div>
  </Modal>

  {error && (
    <div className="mt-4 p-4 bg-red-100 text-red-700 border border-red-300 rounded-md text-center">
      {error}
    </div>
  )}
  {success && (
    <div className="mt-6 p-4 bg-green-100 text-green-700 border border-green-300 rounded-md text-center">
      Registered Successfully!
    </div>
  )}
</div>


  );
};

export default ResumeForm;
