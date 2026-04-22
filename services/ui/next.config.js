/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  output: process.env.ELECTRON_BUILD === 'true' ? 'export' : undefined,

  images: {
    unoptimized: process.env.ELECTRON_BUILD === 'true',
  },

  env: {
    NEXT_PUBLIC_APP_NAME: 'DCS',
    NEXT_PUBLIC_APP_VERSION: '0.1.0',
  },

  transpilePackages: ['lucide-react'],

  serverExternalPackages: [],
};

module.exports = nextConfig;
