"use client";

import { memo, useCallback, useMemo, useState } from "react";
import { cn } from "@/lib/utils";
import type { components } from "@/types/api";

type ConversationRead = components["schemas"]["ConversationRead"];

interface ConversationItemProps {
  conversation: ConversationRead;
  isActive: boolean;
  onSelect: () => void;
  onDelete: () => void;
}

export const ConversationItem = memo(function ConversationItem({
  conversation,
  isActive,
  onSelect,
  onDelete,
}: ConversationItemProps) {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  // Memoize date formatting to avoid recalculation
  const formattedDate = useMemo(() => {
    const date = new Date(conversation.updated_at);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffDays === 0) return "Hoje";
    if (diffDays === 1) return "Ontem";
    if (diffDays < 7) return `${diffDays} dias atrás`;

    return date.toLocaleDateString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  }, [conversation.updated_at]);

  // Memoize handleDelete to maintain reference stability
  const handleDelete = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      if (showDeleteConfirm) {
        onDelete();
        setShowDeleteConfirm(false);
      } else {
        setShowDeleteConfirm(true);
        // Auto-hide confirmation after 3 seconds
        setTimeout(() => setShowDeleteConfirm(false), 3000);
      }
    },
    [showDeleteConfirm, onDelete]
  );

  return (
    <div
      onClick={onSelect}
      className={cn(
        "group relative p-3 cursor-pointer border-l-4 transition-all hover:bg-gray-50",
        {
          "bg-blue-50 border-blue-600": isActive,
          "bg-white border-transparent hover:border-gray-200": !isActive,
        }
      )}
      title={`${conversation.ai_provider} - ${conversation.ai_model}`}
    >
      {/* Main content */}
      <div className="pr-8">
        <h3
          className={cn("font-medium truncate", {
            "text-blue-900": isActive,
            "text-gray-900": !isActive,
          })}
        >
          {conversation.title}
        </h3>

        <div className="flex items-center gap-2 mt-1">
          <span className="text-xs text-gray-500">{formattedDate}</span>
          <span className="text-xs text-gray-400">•</span>
          <span className="text-xs text-gray-500 font-mono">{conversation.ai_provider}</span>
        </div>

        {/* System prompt indicator */}
        {conversation.system_prompt && (
          <div className="mt-1 flex items-center gap-1">
            <svg
              className="w-3 h-3 text-gray-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <span className="text-xs text-gray-400">Prompt personalizado</span>
          </div>
        )}
      </div>

      {/* Delete button */}
      <button
        onClick={handleDelete}
        className={cn(
          "absolute top-3 right-3 p-1 rounded hover:bg-red-100 transition-colors opacity-0 group-hover:opacity-100",
          {
            "bg-red-100 opacity-100": showDeleteConfirm,
          }
        )}
        title={showDeleteConfirm ? "Confirmar exclusão" : "Deletar conversa"}
      >
        <svg
          className={cn("w-4 h-4", {
            "text-red-600": showDeleteConfirm,
            "text-gray-500": !showDeleteConfirm,
          })}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          {showDeleteConfirm ? (
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
            />
          ) : (
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          )}
        </svg>
      </button>

      {showDeleteConfirm && (
        <div className="absolute inset-0 bg-red-50 border-l-4 border-red-600 flex items-center justify-center p-2">
          <span className="text-xs text-red-900 font-medium">Clique novamente para confirmar</span>
        </div>
      )}
    </div>
  );
});
