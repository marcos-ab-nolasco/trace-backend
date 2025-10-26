import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { components } from "@/types/api";
import * as chatApi from "@/lib/api/chat";

// Type aliases
type ConversationRead = components["schemas"]["ConversationRead"];
type ConversationCreate = components["schemas"]["ConversationCreate"];
type ConversationUpdate = components["schemas"]["ConversationUpdate"];
type MessageRead = components["schemas"]["MessageRead"];

// Extended message type with status
export interface ExtendedMessage extends MessageRead {
  status?: "sending" | "sent" | "failed";
  error?: string;
}

interface ChatState {
  // State
  conversations: ConversationRead[];
  currentConversationId: string | null;
  messages: ExtendedMessage[];
  isLoadingConversations: boolean;
  isLoadingMessages: boolean;
  isSendingMessage: boolean;
  error: string | null;

  // Computed
  currentConversation: ConversationRead | null;

  // Actions - Conversations
  loadConversations: () => Promise<void>;
  createConversation: (data: ConversationCreate) => Promise<ConversationRead>;
  updateConversation: (conversationId: string, data: ConversationUpdate) => Promise<void>;
  deleteConversation: (conversationId: string) => Promise<void>;
  selectConversation: (conversationId: string | null) => void;

  // Actions - Messages
  loadMessages: (conversationId: string) => Promise<void>;
  sendMessage: (content: string) => Promise<void>;
  retryMessage: (messageId: string) => Promise<void>;
  removeMessage: (messageId: string) => void;

  // Actions - Utility
  clearError: () => void;
}

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      // Initial state
      conversations: [],
      currentConversationId: null,
      currentConversation: null,
      messages: [],
      isLoadingConversations: false,
      isLoadingMessages: false,
      isSendingMessage: false,
      error: null,

      // Load all conversations
      loadConversations: async () => {
        set({ isLoadingConversations: true, error: null });
        try {
          const response = await chatApi.listConversations();
          set((state) => {
            const conversations = response.conversations;
            const currentConversation =
              conversations.find((c) => c.id === state.currentConversationId) ?? null;
            return {
              conversations,
              currentConversation,
              isLoadingConversations: false,
            };
          });
        } catch (error) {
          const message = error instanceof Error ? error.message : "Failed to load conversations";
          set({ error: message, isLoadingConversations: false });
          throw error;
        }
      },

      // Create a new conversation
      createConversation: async (data: ConversationCreate) => {
        set({ error: null });
        try {
          const conversation = await chatApi.createConversation(data);
          set((state) => ({
            conversations: [conversation, ...state.conversations],
            currentConversationId: conversation.id,
            currentConversation: conversation,
            messages: [], // Clear messages when switching to new conversation
          }));
          return conversation;
        } catch (error) {
          const message = error instanceof Error ? error.message : "Failed to create conversation";
          set({ error: message });
          throw error;
        }
      },

      // Update a conversation
      updateConversation: async (conversationId: string, data: ConversationUpdate) => {
        set({ error: null });
        try {
          const updated = await chatApi.updateConversation(conversationId, data);
          set((state) => {
            const conversations = state.conversations.map((c) =>
              c.id === conversationId ? updated : c
            );
            const isCurrent = state.currentConversationId === conversationId;
            return {
              conversations,
              currentConversation: isCurrent ? updated : state.currentConversation,
            };
          });
        } catch (error) {
          const message = error instanceof Error ? error.message : "Failed to update conversation";
          set({ error: message });
          throw error;
        }
      },

      // Delete a conversation
      deleteConversation: async (conversationId: string) => {
        set({ error: null });
        try {
          await chatApi.deleteConversation(conversationId);
          set((state) => {
            const newConversations = state.conversations.filter((c) => c.id !== conversationId);
            const deletingCurrent = state.currentConversationId === conversationId;
            const currentConversation = deletingCurrent
              ? null
              : (newConversations.find((c) => c.id === state.currentConversationId) ??
                state.currentConversation);
            return {
              conversations: newConversations,
              // If deleting current conversation, clear selection
              currentConversationId: deletingCurrent ? null : state.currentConversationId,
              currentConversation,
              messages: deletingCurrent ? [] : state.messages,
            };
          });
        } catch (error) {
          const message = error instanceof Error ? error.message : "Failed to delete conversation";
          set({ error: message });
          throw error;
        }
      },

      // Select a conversation
      selectConversation: (conversationId: string | null) => {
        set((state) => {
          const currentConversation =
            conversationId === null
              ? null
              : (state.conversations.find((c) => c.id === conversationId) ?? null);
          return {
            currentConversationId: conversationId,
            currentConversation,
            messages: [], // Clear messages when switching conversations
            error: null,
          };
        });
      },

      // Load messages for a conversation
      loadMessages: async (conversationId: string) => {
        // console.log("[DEBUG loadMessages] Starting for conversationId:", conversationId);
        set({ isLoadingMessages: true, error: null });
        try {
          // console.log("[DEBUG loadMessages] Calling API...");
          const response = await chatApi.getMessages(conversationId);
          // console.log("[DEBUG loadMessages] API response:", response);
          // console.log("[DEBUG loadMessages] Messages array:", response.messages);
          // console.log("[DEBUG loadMessages] Messages count:", response.messages?.length ?? 0);
          set({
            messages: response.messages,
            isLoadingMessages: false,
          });
          // console.log("[DEBUG loadMessages] State updated successfully");
        } catch (error) {
          console.error("[DEBUG loadMessages] Error:", error);
          const message = error instanceof Error ? error.message : "Failed to load messages";
          set({ error: message, isLoadingMessages: false });
          throw error;
        }
      },

      // Send a message
      sendMessage: async (content: string) => {
        const { currentConversationId } = get();

        if (!currentConversationId) {
          throw new Error("No conversation selected");
        }

        set({ isSendingMessage: true, error: null });

        // Optimistic update - add user message immediately with sending status
        const optimisticMessage: ExtendedMessage = {
          id: `temp-${Date.now()}`,
          conversation_id: currentConversationId,
          role: "user",
          content,
          tokens_used: null,
          meta: null,
          created_at: new Date().toISOString(),
          status: "sending",
        };

        set((state) => ({
          messages: [...state.messages, optimisticMessage],
        }));

        try {
          // Send message to backend
          const messageResponse = await chatApi.sendMessage(currentConversationId, {
            role: "user",
            content,
          });

          // Remove optimistic message and add both user and assistant messages
          set((state) => ({
            messages: [
              ...state.messages.filter((m) => m.id !== optimisticMessage.id),
              { ...messageResponse.user_message, status: "sent" as const },
              { ...messageResponse.assistant_message, status: "sent" as const },
            ],
            isSendingMessage: false,
          }));
        } catch (error) {
          // Mark message as failed instead of removing it
          const errorMessage = error instanceof Error ? error.message : "Failed to send message";
          set((state) => ({
            messages: state.messages.map((m) =>
              m.id === optimisticMessage.id
                ? { ...m, status: "failed" as const, error: errorMessage }
                : m
            ),
            isSendingMessage: false,
            error: errorMessage,
          }));
          throw error;
        }
      },

      // Retry a failed message
      retryMessage: async (messageId: string) => {
        const { messages, currentConversationId } = get();

        if (!currentConversationId) {
          throw new Error("No conversation selected");
        }

        const failedMessage = messages.find((m) => m.id === messageId);
        if (!failedMessage || failedMessage.status !== "failed") {
          return;
        }

        // Update message status to sending
        set((state) => ({
          messages: state.messages.map((m) =>
            m.id === messageId ? { ...m, status: "sending" as const, error: undefined } : m
          ),
          isSendingMessage: true,
          error: null,
        }));

        try {
          // Send message to backend
          const messageResponse = await chatApi.sendMessage(currentConversationId, {
            role: "user",
            content: failedMessage.content,
          });

          // Replace failed message with successful response (user + assistant)
          set((state) => ({
            messages: [
              ...state.messages.filter((m) => m.id !== messageId),
              { ...messageResponse.user_message, status: "sent" as const },
              { ...messageResponse.assistant_message, status: "sent" as const },
            ],
            isSendingMessage: false,
          }));
        } catch (error) {
          // Mark as failed again
          const errorMessage = error instanceof Error ? error.message : "Failed to send message";
          set((state) => ({
            messages: state.messages.map((m) =>
              m.id === messageId ? { ...m, status: "failed" as const, error: errorMessage } : m
            ),
            isSendingMessage: false,
            error: errorMessage,
          }));
          throw error;
        }
      },

      // Remove a message (usually a failed one)
      removeMessage: (messageId: string) => {
        set((state) => ({
          messages: state.messages.filter((m) => m.id !== messageId),
        }));
      },

      // Clear error
      clearError: () => set({ error: null }),
    }),
    {
      name: "chat-storage",
      // Only persist the current conversation ID
      partialize: (state) => ({
        currentConversationId: state.currentConversationId,
      }),
    }
  )
);
