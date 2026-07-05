/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'cdn.discordapp.com',
      },
      {
        protocol: 'https',
        hostname: 'cdn.trendyol.com',
      },
    ],
  },
  experimental: {
    serverActions: true,
  },
};

export default nextConfig;
