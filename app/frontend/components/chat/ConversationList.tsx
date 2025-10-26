"use client";

import { ConversationItem } from "./ConversationItem";
import type { components } from "@/types/api";

type ConversationRead = components["schemas"]["ConversationRead"];

interface ConversationListProps {
  conversations: ConversationRead[];
  currentConversationId: string | null;
  isLoading: boolean;
  error: string | null;
  onSelectConversation: (id: string) => void;
  onDeleteConversation: (id: string) => void;
  onNewConversation: () => void;
  onRetry?: () => void;
}

export function ConversationList({
  conversations,
  currentConversationId,
  isLoading,
  error,
  onSelectConversation,
  onDeleteConversation,
  onNewConversation,
  onRetry,
}: ConversationListProps) {
  // Loading state
  if (isLoading) {
    return (
      <div className="flex flex-col h-full bg-white">
        {/* Header */}
        <div className="p-4 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900">Conversas</h2>
            <button
              disabled
              className="px-4 py-2 bg-gray-300 text-white rounded-lg font-medium cursor-not-allowed"
            >
              + Nova
            </button>
          </div>
        </div>

        {/* Loading skeleton */}
        <div className="flex-1 overflow-y-auto p-2 space-y-2">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="animate-pulse p-3 bg-gray-100 rounded">
              <div className="h-4 bg-gray-300 rounded w-3/4 mb-2"></div>
              <div className="h-3 bg-gray-200 rounded w-1/2"></div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="flex flex-col h-full bg-white">
        {/* Header */}
        <div className="p-4 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900">Conversas</h2>
            <button
              onClick={onNewConversation}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors"
            >
              + Nova
            </button>
          </div>
        </div>

        {/* Error message */}
        <div className="flex-1 flex items-center justify-center p-4">
          <div className="text-center">
            <svg
              className="w-12 h-12 mx-auto mb-3 text-red-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <p className="text-sm font-medium text-gray-900 mb-1">Erro ao carregar conversas</p>
            <p className="text-xs text-gray-600 mb-3">{error}</p>
            {onRetry && (
              <button
                onClick={onRetry}
                className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                Tentar novamente
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-white">
      {/* Header */}
      <div className="p-4 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Conversas</h2>
          <button
            onClick={onNewConversation}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors text-sm"
          >
            + Nova
          </button>
        </div>
      </div>

      {/* Conversations list */}
      <div className="flex-1 overflow-y-auto">
        {conversations.length === 0 ? (
          // Empty state
          <div className="flex items-center justify-center h-full p-4">
            <div className="text-center">
              <svg
                className="w-16 h-16 mx-auto mb-4 text-gray-300"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
                />
              </svg>
              <p className="text-sm font-medium text-gray-900 mb-1">Nenhuma conversa ainda</p>
              <p className="text-xs text-gray-600 mb-4">
                Clique em &quot;+ Nova&quot; para começar
              </p>
            </div>
          </div>
        ) : (
          // Conversation items
          <div className="divide-y divide-gray-100">
            {conversations.map((conversation) => (
              <ConversationItem
                key={conversation.id}
                conversation={conversation}
                isActive={conversation.id === currentConversationId}
                onSelect={() => onSelectConversation(conversation.id)}
                onDelete={() => onDeleteConversation(conversation.id)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
