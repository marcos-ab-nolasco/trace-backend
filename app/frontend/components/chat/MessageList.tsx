"use client";

import { useEffect, useRef } from "react";
import { MessageBubble } from "./MessageBubble";
import type { ExtendedMessage } from "@/store/chat";

interface MessageListProps {
  messages: ExtendedMessage[];
  isLoading: boolean;
  onRetryMessage?: (messageId: string) => void;
  onRemoveMessage?: (messageId: string) => void;
}

export function MessageList({
  messages,
  isLoading,
  onRetryMessage,
  onRemoveMessage,
}: MessageListProps) {
  // console.log("[DEBUG MessageList] Rendered with:", {
  //   messagesCount: messages.length,
  //   isLoading,
  //   messages: messages,
  // });

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    // console.log("[DEBUG MessageList useEffect] Messages changed, count:", messages.length);
    // Small delay to ensure DOM is updated
    const timer = setTimeout(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    }, 100);
    return () => clearTimeout(timer);
  }, [messages]);

  // Loading skeleton
  if (isLoading) {
    return (
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className={`flex ${i % 2 === 0 ? "justify-end" : "justify-start"}`}>
            <div className="animate-pulse">
              <div
                className={`h-16 rounded-lg ${
                  i % 2 === 0 ? "bg-blue-200 w-64" : "bg-gray-200 w-72"
                }`}
              ></div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  // Empty state
  if (messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="text-center text-gray-500">
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
              d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
            />
          </svg>
          <p className="text-lg font-medium">Nenhuma mensagem ainda</p>
          <p className="text-sm mt-1">Envie uma mensagem para começar a conversa</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 chat-scrollbar">
      {messages.map((message) => (
        <MessageBubble
          key={message.id}
          role={message.role as "user" | "assistant" | "system"}
          content={message.content}
          timestamp={message.created_at}
          tokensUsed={message.tokens_used}
          status={message.status}
          error={message.error}
          onRetry={onRetryMessage ? () => onRetryMessage(message.id) : undefined}
          onRemove={onRemoveMessage ? () => onRemoveMessage(message.id) : undefined}
        />
      ))}
      {/* Invisible element to scroll to */}
      <div ref={messagesEndRef} />
    </div>
  );
}
