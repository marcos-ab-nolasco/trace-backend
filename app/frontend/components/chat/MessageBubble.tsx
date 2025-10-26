import { memo, useMemo } from "react";
import { cn } from "@/lib/utils";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { CodeBlock } from "./CodeBlock";

interface MessageBubbleProps {
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
  tokensUsed?: number | null;
  status?: "sending" | "sent" | "failed";
  error?: string;
  onRetry?: () => void;
  onRemove?: () => void;
}

export const MessageBubble = memo(function MessageBubble({
  role,
  content,
  timestamp,
  tokensUsed,
  status = "sent",
  error,
  onRetry,
  onRemove,
}: MessageBubbleProps) {
  const isUser = role === "user";
  const isSystem = role === "system";
  const isFailed = status === "failed";
  const isSending = status === "sending";

  // Memoize timestamp formatting to avoid recalculation on every render
  const formattedTimestamp = useMemo(() => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return "agora";
    if (diffMins < 60) return `há ${diffMins}m`;
    if (diffHours < 24) return `há ${diffHours}h`;
    if (diffDays < 7) return `há ${diffDays}d`;

    return date.toLocaleDateString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }, [timestamp]);

  return (
    <div
      className={cn("flex w-full mb-4 animate-fade-in-up", {
        "justify-end": isUser,
        "justify-start": !isUser,
        "justify-center": isSystem,
      })}
    >
      <div className="max-w-[80%]">
        <div
          className={cn("rounded-lg px-4 py-2 relative", {
            "bg-blue-600 text-white": isUser && !isFailed,
            "bg-red-600 text-white": isUser && isFailed,
            "bg-gray-200 text-gray-900": !isUser && !isSystem,
            "bg-yellow-100 text-yellow-900 text-sm italic": isSystem,
            "opacity-60": isSending,
          })}
        >
          {/* Sending indicator */}
          {isSending && (
            <div className="absolute -left-8 top-1/2 -translate-y-1/2">
              <svg
                className="animate-spin h-5 w-5 text-blue-600"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                ></circle>
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                ></path>
              </svg>
            </div>
          )}

          {/* Message content */}
          <div className="prose prose-sm prose-invert max-w-none">
            {role === "assistant" ? (
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  code: CodeBlock,
                  p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                  ul: ({ children }) => <ul className="list-disc ml-4 mb-2">{children}</ul>,
                  ol: ({ children }) => <ol className="list-decimal ml-4 mb-2">{children}</ol>,
                  li: ({ children }) => <li className="mb-1">{children}</li>,
                  h1: ({ children }) => (
                    <h1 className="text-xl font-bold mb-2 mt-4 first:mt-0">{children}</h1>
                  ),
                  h2: ({ children }) => (
                    <h2 className="text-lg font-bold mb-2 mt-3 first:mt-0">{children}</h2>
                  ),
                  h3: ({ children }) => (
                    <h3 className="text-base font-bold mb-2 mt-2 first:mt-0">{children}</h3>
                  ),
                  blockquote: ({ children }) => (
                    <blockquote className="border-l-4 border-gray-600 pl-4 italic my-2">
                      {children}
                    </blockquote>
                  ),
                  a: ({ children, href }) => (
                    <a
                      href={href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-400 hover:text-blue-300 underline"
                    >
                      {children}
                    </a>
                  ),
                  table: ({ children }) => (
                    <div className="overflow-x-auto my-2">
                      <table className="min-w-full border border-gray-700">{children}</table>
                    </div>
                  ),
                  th: ({ children }) => (
                    <th className="border border-gray-700 px-3 py-2 bg-gray-800 font-bold">
                      {children}
                    </th>
                  ),
                  td: ({ children }) => (
                    <td className="border border-gray-700 px-3 py-2">{children}</td>
                  ),
                }}
              >
                {content}
              </ReactMarkdown>
            ) : (
              <div className="whitespace-pre-wrap break-words">{content}</div>
            )}
          </div>

          {/* Footer with timestamp and tokens */}
          <div
            className={cn("flex items-center gap-2 mt-1 text-xs", {
              "text-blue-100": isUser && !isFailed,
              "text-red-100": isUser && isFailed,
              "text-gray-600": !isUser && !isSystem,
              "text-yellow-700": isSystem,
            })}
          >
            <span>{formattedTimestamp}</span>

            {/* Tokens badge (only for assistant messages) */}
            {!isUser && !isSystem && tokensUsed !== null && tokensUsed !== undefined && (
              <>
                <span>•</span>
                <span className="font-mono">{tokensUsed} tokens</span>
              </>
            )}

            {/* Failed indicator */}
            {isFailed && (
              <>
                <span>•</span>
                <span>Falha ao enviar</span>
              </>
            )}
          </div>
        </div>

        {/* Error message and retry/remove buttons */}
        {isFailed && (
          <div className="mt-2 flex items-start gap-2 text-sm">
            {error && (
              <div className="flex-1 text-red-600 text-xs">
                <span className="font-medium">Erro:</span> {error}
              </div>
            )}
            <div className="flex gap-2">
              {onRetry && (
                <button
                  onClick={onRetry}
                  className="px-3 py-1 bg-blue-600 text-white rounded text-xs font-medium hover:bg-blue-700 transition-colors"
                >
                  Tentar novamente
                </button>
              )}
              {onRemove && (
                <button
                  onClick={onRemove}
                  className="px-3 py-1 bg-gray-200 text-gray-700 rounded text-xs font-medium hover:bg-gray-300 transition-colors"
                >
                  Remover
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
});
