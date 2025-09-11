import PageTransition from "@/components/animation/PageTransition";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-dvh flex items-center justify-center bg-white">
      <PageTransition>{children}</PageTransition>
    </div>
  );
}
