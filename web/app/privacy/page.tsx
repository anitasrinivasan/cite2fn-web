import type { Metadata } from "next";
import { ContentLayout } from "@/components/ContentLayout";

export const metadata: Metadata = {
  title: "Privacy Policy — cite2fn",
};

export default function Privacy() {
  return (
    <ContentLayout title="Privacy Policy">
      <div className="rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        <strong>Draft — please review with counsel.</strong> This document
        describes the actual data practices of the Service to the best of the
        author&apos;s knowledge, but is not a substitute for a legally
        reviewed privacy notice. Confirm with an attorney before publishing.
      </div>

      <p className="text-xs text-slate-500">Last updated: April 2026.</p>

      <h2 className="mt-8 text-xl font-semibold text-slate-900">
        What we process
      </h2>
      <ul className="list-disc space-y-1 pl-6">
        <li>
          The <code>.docx</code> file you upload, temporarily, for the sole
          purpose of producing your cited output document.
        </li>
        <li>
          The URLs linked inside your document. We send HTTPS requests to
          those URLs to retrieve publicly available bibliographic metadata
          (title, authors, journal, year).
        </li>
        <li>
          Your Anthropic (Claude) API key <em>only when you provide it</em>.
          It is held in server memory for the duration of your job and
          discarded when the job ends. It is never written to disk, logged,
          or transmitted to any party other than Anthropic.
        </li>
        <li>
          Minimal job metadata (job id, selected style and format, phase and
          progress counters) stored in a local SQLite database for the
          lifetime of the job.
        </li>
      </ul>

      <h2 className="mt-8 text-xl font-semibold text-slate-900">
        What we do not do
      </h2>
      <ul className="list-disc space-y-1 pl-6">
        <li>No user accounts. No login. No authentication of any kind.</li>
        <li>No tracking pixels, no analytics, no advertising identifiers.</li>
        <li>No cookies (beyond what the web framework may require for a session).</li>
        <li>No selling or sharing of your data with third parties other than what is strictly required to fulfill your request (see below).</li>
      </ul>

      <h2 className="mt-8 text-xl font-semibold text-slate-900">
        Third parties involved in processing
      </h2>
      <ul className="list-disc space-y-1 pl-6">
        <li>
          <strong>Anthropic</strong> — if you provide a Claude API key, your
          citation text and surrounding context are sent to Anthropic&apos;s
          API for formatting. See Anthropic&apos;s privacy policy.
        </li>
        <li>
          <strong>Groq</strong> — if you choose the free fallback, the same
          information is sent to Groq, which hosts the open-source model.
        </li>
        <li>
          <strong>Source publishers</strong> — the operators of the websites
          you linked will see a standard HTTP request from our server
          fetching their public metadata.
        </li>
      </ul>

      <h2 className="mt-8 text-xl font-semibold text-slate-900">
        Retention and deletion
      </h2>
      <p>
        Your uploaded document, the generated output document, and the job
        metadata are all deleted automatically after 24 hours. You can also
        close the browser tab at any time and the server will still purge
        your data on the same schedule. We do not keep backups of uploads.
      </p>

      <h2 className="mt-8 text-xl font-semibold text-slate-900">
        Your rights
      </h2>
      <p>
        Because we do not maintain accounts and all data is deleted within 24
        hours, there is typically nothing to retrieve, correct, or erase.
        If you believe your data has been processed incorrectly, or if you
        need a specific record deleted before the automatic cutoff, please
        contact the author — see below.
      </p>

      <h2 className="mt-8 text-xl font-semibold text-slate-900">
        Contact
      </h2>
      <p>
        For questions about this policy or to raise a privacy concern,
        contact the author via{" "}
        <a
          href="https://www.anitasrinivasan.com"
          target="_blank"
          rel="noopener noreferrer"
          className="underline-offset-4 hover:text-slate-900 hover:underline"
        >
          anitasrinivasan.com
        </a>
        .
      </p>

      <h2 className="mt-8 text-xl font-semibold text-slate-900">
        Changes to this policy
      </h2>
      <p>
        We may update this policy as the service evolves. The date above
        reflects the most recent update.
      </p>
    </ContentLayout>
  );
}
