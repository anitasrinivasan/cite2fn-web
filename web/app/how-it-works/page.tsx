import type { Metadata } from "next";
import { ContentLayout } from "@/components/ContentLayout";

export const metadata: Metadata = {
  title: "How it works — cite2fn",
};

export default function HowItWorks() {
  return (
    <ContentLayout title="How it works">
      <p>
        cite2fn takes a Word document in which you&apos;ve linked your sources
        — hyperlinks to papers, parenthetical author-date references, or
        inline names — and returns a document with every citation formatted
        properly as footnotes, endnotes, or a reference list. The whole thing
        happens in five steps, which you can follow along with in the progress
        bar.
      </p>

      <h2 className="mt-10 text-xl font-semibold text-slate-900 dark:text-slate-100">
        The pipeline
      </h2>

      <ol className="list-decimal space-y-3 pl-6">
        <li>
          <span className="font-medium text-slate-900 dark:text-slate-100">Detect.</span> We scan
          every paragraph for citations: hyperlinks to sources, parenthetical
          author-date markers like <code>(Smith 2023)</code>, inline mentions
          like <code>Smith (2023) argued</code>, and any existing footnotes
          that still have bare URLs instead of proper citations.
        </li>
        <li>
          <span className="font-medium text-slate-900 dark:text-slate-100">Fetch metadata.</span>{" "}
          For each linked URL we pull title, authors, journal, year, and other
          bibliographic fields from the source page. We canonicalize URLs
          (stripping library-proxy wrappers, CDN tokens, and other
          non-permanent variants) so the final citation points at a stable
          address.
        </li>
        <li>
          <span className="font-medium text-slate-900 dark:text-slate-100">Format.</span> The
          bibliographic details plus surrounding context go to a language
          model, which writes each citation in the style you picked — Bluebook
          21st or APA 7th — with italics, small caps, and the acronym
          conventions applied correctly.
        </li>
        <li>
          <span className="font-medium text-slate-900 dark:text-slate-100">Review.</span> Before
          any footnote is inserted into your document, you see every
          formatted citation in a table alongside the original source URL.
          Anything the model flagged as low-confidence is highlighted in
          amber. Edit inline, then accept.
        </li>
        <li>
          <span className="font-medium text-slate-900 dark:text-slate-100">Assemble.</span> We
          insert footnotes at the right position (after the relevant
          punctuation, with the citation phrase removed from the body),
          renumber, and merge adjacent citations per Bluebook convention. You
          download the new <code>.docx</code>.
        </li>
      </ol>

      <h2 className="mt-10 text-xl font-semibold text-slate-900 dark:text-slate-100">
        What you can configure
      </h2>

      <ul className="list-disc space-y-2 pl-6">
        <li>
          <span className="font-medium text-slate-900 dark:text-slate-100">Style:</span> Bluebook
          21st edition or APA 7th edition.
        </li>
        <li>
          <span className="font-medium text-slate-900 dark:text-slate-100">Output format:</span>{" "}
          footnotes, endnotes, or a list of references appended to the
          document.
        </li>
        <li>
          <span className="font-medium text-slate-900 dark:text-slate-100">
            Formatting engine:
          </span>{" "}
          paste your own Anthropic (Claude) API key for best quality, or use
          the free fallback backed by an open-source model. Your key is held
          in memory for the duration of the job and is never written to disk.
        </li>
        <li>
          <span className="font-medium text-slate-900 dark:text-slate-100">Advanced:</span>{" "}
          optionally keep your original References section in the output
          document.
        </li>
      </ul>

      <h2 className="mt-10 text-xl font-semibold text-slate-900 dark:text-slate-100">
        What it is not
      </h2>
      <p>
        This is a strong first pass, not a final draft. Scraped metadata is
        imperfect, and style nuances vary by publication. Always review every
        footnote against the source, especially pin cites, author lists, and
        short-form conventions (<em>Id.</em>, <em>supra</em>). The tool makes
        the tedious 80% cheap; the last 20% is still yours.
      </p>

      <p className="mt-16 text-sm text-slate-500 dark:text-slate-400">
        Built by{" "}
        <a
          href="https://www.anitasrinivasan.com"
          target="_blank"
          rel="noopener noreferrer"
          className="underline-offset-4 hover:text-slate-900 hover:underline dark:hover:text-slate-100"
        >
          Anita Srinivasan
        </a>
        .
      </p>
    </ContentLayout>
  );
}
