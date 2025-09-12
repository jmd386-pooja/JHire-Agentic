import PageTransition from "@/components/animation/PageTransition";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <main className="min-h-dvh w-full bg-white">
      <PageTransition>{children}</PageTransition>
    </main>
  );
}
