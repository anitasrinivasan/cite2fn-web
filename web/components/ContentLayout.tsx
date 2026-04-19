import { Footer } from "@/components/Footer";
import { Header } from "@/components/Header";

export function ContentLayout({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      <Header />
      <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-12">
        <h1 className="mb-8 text-3xl font-semibold tracking-tight text-slate-900">
          {title}
        </h1>
        <div className="space-y-5 text-slate-700 leading-relaxed">
          {children}
        </div>
      </main>
      <Footer />
    </div>
  );
}
