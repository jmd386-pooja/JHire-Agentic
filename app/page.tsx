import { redirect } from 'next/navigation';

export default function Home() {
  // Redirect to /login on page load
  
  redirect('/login');

  return null; // This will never be displayed
}