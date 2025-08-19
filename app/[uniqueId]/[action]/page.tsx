'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { CheckCircle, XCircle, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function CandidateActionPage() {
  const params = useParams();
  const router = useRouter();
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [message, setMessage] = useState('');
  const [action, setAction] = useState<'accept' | 'decline' | null>(null);

  useEffect(() => {
    const fetchActionResult = async () => {
      try {
        const uniqueId = params.uniqueId as string;
        const action = params.action as string;

        if (!uniqueId || !action) {
          setStatus('error');
          setMessage('Invalid request parameters');
          return;
        }
        setAction(action as 'accept' | 'decline');

        // Call the API route with uniqueId and action
        const response = await fetch(`/api/${uniqueId}/${action}`);
        const data = await response.json();

        if (response.ok) {
          setStatus('success');
          setMessage(data.message);
        } else {
          setStatus('error');
          setMessage(data.message || 'An error occurred');
        }
      } catch (error) {
        console.error('Error:', error);
        setStatus('error');
        setMessage('An error occurred while processing your request');
      }
    };

    fetchActionResult();
  }, [params.uniqueId, params.action]);

  const iconVariants = {
    hidden: { scale: 0, rotate: -180 },
    visible: {
      scale: 1,
      rotate: 0,
      transition: { type: 'spring', stiffness: 260, damping: 20 },
    },
  };
  const checkmarkVariants = {
    hidden: { scale: 0, rotate: -180 },
    visible: {
      scale: 1,
      rotate: 0,
      transition: { type: 'spring', stiffness: 260, damping: 20 },
    },
  };

  const crossVariants = {
    hidden: { scale: 0 },
    visible: {
      scale: 1,
      transition: { type: 'spring', stiffness: 200, damping: 15 },
    },
  };

  const crossLineVariants = {
    hidden: { pathLength: 0 },
    visible: { pathLength: 1, transition: { duration: 0.5 } },
  };


  const messageVariants = {
    hidden: { opacity: 0, y: 50 },
    visible: { opacity: 1, y: 0, transition: { delay: 0.3 } },
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-r from-blue-100 to-purple-100">
      <motion.div
        className="bg-white p-8 rounded-lg shadow-xl flex flex-col items-center"
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.5 }}
      >
        {status === 'loading' && (
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
          >
            <Loader2 className="w-16 h-16 text-blue-500" />
          </motion.div>
        )}
        {/* {status === 'success' && (
          <motion.div variants={iconVariants} initial="hidden" animate="visible">
            <CheckCircle className="w-16 h-16 text-green-500" />
          </motion.div>
        )} */}
                {status === 'success' && action === 'accept' && (
          <motion.div variants={checkmarkVariants} initial="hidden" animate="visible">
            <CheckCircle className="w-16 h-16 text-green-500" />
          </motion.div>
        )}
        {status === 'success' && action === 'decline' && (
          <motion.div className="relative w-16 h-16" variants={crossVariants} initial="hidden" animate="visible">
            <svg className="absolute w-16 h-16 text-red-500" viewBox="0 0 24 24">
              <motion.line
                x1="4"
                y1="4"
                x2="20"
                y2="20"
                stroke="currentColor"
                strokeWidth="2"
                variants={crossLineVariants}
                initial="hidden"
                animate="visible"
              />
              <motion.line
                x1="4"
                y1="20"
                x2="20"
                y2="4"
                stroke="currentColor"
                strokeWidth="2"
                variants={crossLineVariants}
                initial="hidden"
                animate="visible"
              />
            </svg>
          </motion.div>
        )}
        {status === 'error' && (
          <motion.div variants={iconVariants} initial="hidden" animate="visible">
            <XCircle className="w-16 h-16 text-red-500" />
          </motion.div>
        )}
        <motion.h1
          className="mt-4 text-2xl font-bold text-gray-800"
          variants={messageVariants}
          initial="hidden"
          animate="visible"
        >
          {status === 'loading' ? 'Processing...' : status === 'success' ? 'Action Completed' : 'Error'}
        </motion.h1>
        <motion.p
          className="mt-2 text-gray-600 text-center"
          variants={messageVariants}
          initial="hidden"
          animate="visible"
        >
          {message}
        </motion.p>
        {status !== 'loading' && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.5 }}
          >
          </motion.div>
        )}
      </motion.div>
    </div>
  );
}
