import { useEffect, useRef, useState } from "react";
import { AppLayout } from "@/components/layout/AppLayout";
import { deleteRagDocument, listRagDocuments, setRagDocumentActive, uploadRagDocument, type RagDocumentRow } from "@/lib/services";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";

export default function KnowledgeBase() {
  const [documents, setDocuments] = useState<RagDocumentRow[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const loadDocuments = () => {
    void listRagDocuments().then(setDocuments);
  };

  useEffect(() => {
    loadDocuments();
  }, []);

  const onPickFile = async (file: File) => {
    setUploading(true);
    const result = await uploadRagDocument(file, file.name);
    setUploading(false);
    if (!result.ok) {
      toast.error("Could not upload document.", { description: result.error });
      return;
    }
    toast.success("Document uploaded.");
    loadDocuments();
  };

  return (
    <AppLayout title="Knowledge Base" subtitle="Manage HR policy documents for MARK RAG answers">
      <div className="px-6 lg:px-10 py-8 max-w-5xl space-y-6">
        <div className="rounded-2xl border border-border bg-card p-5 flex items-center justify-between gap-4">
          <div>
            <div className="text-sm font-medium">Policy document management</div>
            <div className="text-xs text-muted-foreground mt-1">Upload PDF/DOCX files used by semantic retrieval.</div>
          </div>
          <div>
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,.docx"
              className="hidden"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) {
                  void onPickFile(file);
                }
                event.target.value = "";
              }}
            />
            <Button type="button" disabled={uploading} onClick={() => fileRef.current?.click()}>
              {uploading ? "Uploading..." : "Upload document"}
            </Button>
          </div>
        </div>

        <div className="rounded-2xl border border-border bg-card overflow-hidden">
          <div className="grid grid-cols-[1fr_120px_120px_100px] px-5 py-3 text-[10px] uppercase tracking-[0.18em] text-muted-foreground border-b border-border">
            <div>Document</div>
            <div>Chunks</div>
            <div>Status</div>
            <div />
          </div>
          <ul className="divide-y divide-border">
            {documents.map((doc) => (
              <li key={doc.id} className="grid grid-cols-[1fr_120px_120px_100px] gap-3 items-center px-5 py-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <div className="text-sm font-medium truncate">{doc.title}</div>
                    <FreshnessBadge updatedAt={doc.updated_at || doc.created_at} />
                  </div>
                  <div className="text-xs text-muted-foreground">{new Date(doc.created_at).toLocaleString()}</div>
                </div>
                <div className="text-sm">{doc.chunks_count}</div>
                <button
                  type="button"
                  className={`text-xs px-2 py-1 rounded-md border ${doc.is_active ? "bg-emerald-soft text-emerald border-emerald/40" : "bg-secondary text-muted-foreground border-border"}`}
                  disabled={busyId === doc.id}
                  onClick={async () => {
                    setBusyId(doc.id);
                    const ok = await setRagDocumentActive(doc.id, !doc.is_active);
                    setBusyId(null);
                    if (!ok) {
                      toast.error("Could not update status.");
                      return;
                    }
                    loadDocuments();
                  }}
                >
                  {doc.is_active ? "Active" : "Inactive"}
                </button>
                <button
                  type="button"
                  className="text-xs text-danger underline justify-self-start"
                  disabled={busyId === doc.id}
                  onClick={async () => {
                    setBusyId(doc.id);
                    const ok = await deleteRagDocument(doc.id);
                    setBusyId(null);
                    if (!ok) {
                      toast.error("Could not delete document.");
                      return;
                    }
                    toast.success("Document deleted.");
                    loadDocuments();
                  }}
                >
                  Delete
                </button>
              </li>
            ))}
            {documents.length === 0 && (
              <li className="px-5 py-8 text-sm text-muted-foreground">No documents uploaded yet.</li>
            )}
          </ul>
        </div>
      </div>
    </AppLayout>
  );
}

// Matches POLICY_OUTDATED_DAYS in rag_orchestrator.py — the same threshold
// the backend uses to warn the chat user, surfaced visually here so HR sees
// stale documents at a glance instead of waiting for someone to ask a
// question that touches them.
const FRESHNESS_WARN_DAYS = 365;

function FreshnessBadge({ updatedAt }: { updatedAt: string | null }) {
  if (!updatedAt) return null;
  const ts = Date.parse(updatedAt);
  if (Number.isNaN(ts)) return null;
  const ageDays = (Date.now() - ts) / 86_400_000;
  if (ageDays < FRESHNESS_WARN_DAYS) return null;
  return (
    <span
      className="text-[10px] uppercase tracking-wide px-2 py-0.5 rounded-md bg-warning-soft text-warning font-medium"
      title={`Last updated ${Math.floor(ageDays)} days ago — chat answers will warn users that this policy may be outdated.`}
    >
      Stale &gt; {Math.round(ageDays / 30)}mo
    </span>
  );
}
