"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { useChatStore } from "@/store/chat";
import { Sidebar } from "@/components/chat/Sidebar";
import { ChatInterface } from "@/components/chat/ChatInterface";

export default function ChatPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: isAuthLoading } = useAuth();

  const {
    conversations,
    currentConversationId,
    messages,
    isLoadingConversations,
    isLoadingMessages,
    isSendingMessage,
    error,
    currentConversation,
    loadConversations,
    createConversation,
    updateConversation,
    deleteConversation,
    selectConversation,
    loadMessages,
    sendMessage,
    retryMessage,
    removeMessage,
    clearError,
  } = useChatStore();

  // console.log("[DEBUG page.tsx useChatStore]", {
  //   conversationsCount: conversations.length,
  //   currentConversationId,
  //   currentConversationExists: currentConversation !== null,
  //   currentConversationId_fromObject: currentConversation?.id,
  //   messagesCount: messages.length,
  // });

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!isAuthLoading && !isAuthenticated) {
      router.push("/login");
    }
  }, [isAuthenticated, isAuthLoading, router]);

  // Load conversations on mount
  useEffect(() => {
    if (isAuthenticated) {
      loadConversations().catch((error) => {
        console.error("Failed to load conversations:", error);
      });
    }
  }, [isAuthenticated, loadConversations]);

  // Load messages when conversation changes
  useEffect(() => {
    // console.log("[DEBUG useEffect] Triggered with currentConversationId:", currentConversationId);
    // console.log("[DEBUG useEffect] Current messages count:", messages.length);
    if (currentConversationId) {
      // console.log("[DEBUG useEffect] Calling loadMessages...");
      loadMessages(currentConversationId).catch((error) => {
        console.error("Failed to load messages:", error);
      });
    } else {
      console.log("[DEBUG useEffect] No conversation selected, skipping");
    }
  }, [currentConversationId, loadMessages]);

  // Handle conversation selection
  const handleSelectConversation = (id: string) => {
    selectConversation(id);
  };

  // Handle create conversation
  const handleCreateConversation = async (data: {
    title: string;
    ai_provider: string;
    ai_model: string;
    system_prompt?: string | null;
  }) => {
    try {
      await createConversation(data);
    } catch (error) {
      console.error("Failed to create conversation:", error);
      throw error;
    }
  };

  // Handle conversation deletion
  const handleDeleteConversation = async (id: string) => {
    try {
      await deleteConversation(id);
    } catch (error) {
      console.error("Failed to delete conversation:", error);
    }
  };

  // Handle send message
  const handleSendMessage = async (content: string) => {
    if (!currentConversationId) return;

    try {
      await sendMessage(content);
    } catch (error) {
      console.error("Failed to send message:", error);
      // Error is already set in store
    }
  };

  // Handle update conversation
  const handleUpdateConversation = async (data: {
    title?: string | null;
    system_prompt?: string | null;
  }) => {
    if (!currentConversationId) return;

    try {
      await updateConversation(currentConversationId, data);
    } catch (error) {
      console.error("Failed to update conversation:", error);
      throw error;
    }
  };

  // Loading state
  if (isAuthLoading || !isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <svg
            className="animate-spin h-12 w-12 mx-auto mb-4 text-blue-600"
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
          <p className="text-gray-600">Carregando...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen flex overflow-hidden bg-gray-50">
      {/* Sidebar */}
      <Sidebar
        conversations={conversations}
        currentConversationId={currentConversationId}
        isLoading={isLoadingConversations}
        error={error}
        onSelectConversation={handleSelectConversation}
        onDeleteConversation={handleDeleteConversation}
        onCreateConversation={handleCreateConversation}
        onRetry={() => {
          clearError();
          loadConversations();
        }}
      />

      {/* Main Chat Interface */}
      <ChatInterface
        conversation={currentConversation}
        messages={messages}
        isLoadingMessages={isLoadingMessages}
        isSendingMessage={isSendingMessage}
        onSendMessage={handleSendMessage}
        onUpdateConversation={handleUpdateConversation}
        onRetryMessage={retryMessage}
        onRemoveMessage={removeMessage}
      />

      {/* Error Toast (if needed) */}
      {error && (
        <div className="fixed bottom-4 right-4 bg-red-600 text-white px-6 py-3 rounded-lg shadow-lg flex items-center gap-3 max-w-md z-50">
          <svg className="w-5 h-5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path
              fillRule="evenodd"
              d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
              clipRule="evenodd"
            />
          </svg>
          <span className="flex-1">{error}</span>
          <button onClick={clearError} className="text-white hover:text-red-200 transition-colors">
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                clipRule="evenodd"
              />
            </svg>
          </button>
        </div>
      )}
    </div>
  );
}
