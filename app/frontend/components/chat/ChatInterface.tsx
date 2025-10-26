"use client";

import { useState } from "react";
import { MessageList } from "./MessageList";
import { MessageInput } from "./MessageInput";
import { EditConversationModal } from "./EditConversationModal";
import type { components } from "@/types/api";
import type { ExtendedMessage } from "@/store/chat";

type ConversationRead = components["schemas"]["ConversationRead"];
type ConversationUpdate = components["schemas"]["ConversationUpdate"];

interface ChatInterfaceProps {
  conversation: ConversationRead | null;
  messages: ExtendedMessage[];
  isLoadingMessages: boolean;
  isSendingMessage: boolean;
  onSendMessage: (content: string) => void;
  onUpdateConversation: (data: ConversationUpdate) => Promise<void>;
  onRetryMessage?: (messageId: string) => void;
  onRemoveMessage?: (messageId: string) => void;
}

export function ChatInterface({
  conversation,
  messages,
  isLoadingMessages,
  isSendingMessage,
  onSendMessage,
  onUpdateConversation,
  onRetryMessage,
  onRemoveMessage,
}: ChatInterfaceProps) {
  // console.log("[DEBUG ChatInterface] Rendered with:", {
  //   conversationId: conversation?.id,
  //   messagesCount: messages.length,
  //   isLoadingMessages,
  //   messages: messages,
  // });

  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);

  const handleUpdateConversation = async (data: ConversationUpdate) => {
    setIsUpdating(true);
    try {
      await onUpdateConversation(data);
      setIsEditModalOpen(false);
    } catch (error) {
      console.error("Failed to update conversation:", error);
    } finally {
      setIsUpdating(false);
    }
  };

  // Empty state - no conversation selected
  if (!conversation) {
    return (
      <div className="flex-1 flex items-center justify-center bg-gray-50 p-8">
        <div className="text-center max-w-md">
          <svg
            className="w-24 h-24 mx-auto mb-6 text-gray-300"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
            />
          </svg>
          <h3 className="text-xl font-semibold text-gray-900 mb-2">Bem-vindo ao Chat com IA</h3>
          <p className="text-gray-600 mb-1">
            Selecione uma conversa na barra lateral ou crie uma nova
          </p>
          <p className="text-sm text-gray-500">
            Converse com diferentes modelos de IA: OpenAI, Anthropic, Gemini e Grok
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col bg-white">
      {/* Header */}
      <div className="border-b border-gray-200 bg-white px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex-1 min-w-0">
            <h2 className="text-lg font-semibold text-gray-900 truncate">{conversation.title}</h2>
            <div className="flex items-center gap-3 mt-1">
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                <svg className="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M2 5a2 2 0 012-2h7a2 2 0 012 2v4a2 2 0 01-2 2H9l-3 3v-3H4a2 2 0 01-2-2V5z" />
                  <path d="M15 7v2a4 4 0 01-4 4H9.828l-1.766 1.767c.28.149.599.233.938.233h2l3 3v-3h2a2 2 0 002-2V9a2 2 0 00-2-2h-1z" />
                </svg>
                {conversation.ai_provider}
              </span>
              <span className="text-xs text-gray-500 font-mono">{conversation.ai_model}</span>
              {conversation.system_prompt && (
                <span className="inline-flex items-center text-xs text-gray-500">
                  <svg
                    className="w-3 h-3 mr-1"
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
                  Prompt personalizado
                </span>
              )}
            </div>
          </div>
          <button
            onClick={() => setIsEditModalOpen(true)}
            className="ml-4 p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
            title="Editar conversa"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
              />
            </svg>
          </button>
        </div>
      </div>

      {/* Messages */}
      <MessageList
        messages={messages}
        isLoading={isLoadingMessages}
        onRetryMessage={onRetryMessage}
        onRemoveMessage={onRemoveMessage}
      />

      {/* Input */}
      <MessageInput
        onSend={onSendMessage}
        disabled={isSendingMessage || isLoadingMessages}
        placeholder={isSendingMessage ? "Aguardando resposta..." : "Digite sua mensagem..."}
      />

      {/* Edit Modal */}
      <EditConversationModal
        isOpen={isEditModalOpen}
        conversation={conversation}
        onClose={() => setIsEditModalOpen(false)}
        onSubmit={handleUpdateConversation}
        isSubmitting={isUpdating}
      />
    </div>
  );
}
