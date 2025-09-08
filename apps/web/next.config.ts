// /** @type {import('next').NextConfig} */
// const nextConfig = {
//   // output: 'stand alone',
//   eslint: {
//     ignoreDuringBuilds: true,
//   },
//   images: { unoptimized: true },
// };

// module.exports = nextConfig;

import type { NextConfig } from 'next'

/** @type {import('next').NextConfig} */
const nextConfig : NextConfig = {
    reactStrictMode: false, // Disable StrictMode
  };
  
module.exports = nextConfig;