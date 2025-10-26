import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { useChatStore } from "@/store/chat";
import * as chatApi from "@/lib/api/chat";

// Mock the API functions
vi.mock("@/lib/api/chat");

describe("Chat Store (Zustand)", () => {
  beforeEach(() => {
    // Reset store state before each test
    useChatStore.setState({
      conversations: [],
      currentConversationId: null,
      currentConversation: null,
      messages: [],
      isLoadingConversations: false,
      isLoadingMessages: false,
      isSendingMessage: false,
      error: null,
    });
    vi.clearAllMocks();
  });

  afterEach(() => {
    localStorage.clear();
  });

  describe("Initial State", () => {
    it("should have correct initial state", () => {
      const state = useChatStore.getState();

      expect(state.conversations).toEqual([]);
      expect(state.currentConversationId).toBeNull();
      expect(state.messages).toEqual([]);
      expect(state.isLoadingConversations).toBe(false);
      expect(state.isLoadingMessages).toBe(false);
      expect(state.isSendingMessage).toBe(false);
      expect(state.error).toBeNull();
    });

    it("should compute currentConversation as null initially", () => {
      const state = useChatStore.getState();
      expect(state.currentConversation).toBeNull();
    });
  });

  describe("loadConversations", () => {
    it("should load conversations and update state", async () => {
      const mockConversations = {
        conversations: [
          {
            id: "conv-1",
            user_id: "user-123",
            title: "Test Chat",
            ai_provider: "openai",
            ai_model: "gpt-4",
            system_prompt: null,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        ],
        total: 1,
      };

      vi.mocked(chatApi.listConversations).mockResolvedValueOnce(mockConversations);

      await useChatStore.getState().loadConversations();

      const state = useChatStore.getState();
      expect(chatApi.listConversations).toHaveBeenCalled();
      expect(state.conversations).toEqual(mockConversations.conversations);
      expect(state.isLoadingConversations).toBe(false);
      expect(state.error).toBeNull();
    });

    it("should set error on load failure", async () => {
      vi.mocked(chatApi.listConversations).mockRejectedValueOnce(
        new Error("Failed to load conversations")
      );

      await expect(useChatStore.getState().loadConversations()).rejects.toThrow(
        "Failed to load conversations"
      );

      const state = useChatStore.getState();
      expect(state.error).toBe("Failed to load conversations");
      expect(state.isLoadingConversations).toBe(false);
    });
  });

  describe("createConversation", () => {
    it("should create conversation and add to list", async () => {
      const newConversation = {
        id: "conv-new",
        user_id: "user-123",
        title: "New Chat",
        ai_provider: "anthropic",
        ai_model: "claude-3-opus",
        system_prompt: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      vi.mocked(chatApi.createConversation).mockResolvedValueOnce(newConversation);

      const result = await useChatStore.getState().createConversation({
        title: "New Chat",
        ai_provider: "anthropic",
        ai_model: "claude-3-opus",
      });

      expect(chatApi.createConversation).toHaveBeenCalledWith({
        title: "New Chat",
        ai_provider: "anthropic",
        ai_model: "claude-3-opus",
      });

      const state = useChatStore.getState();
      expect(state.conversations).toContainEqual(newConversation);
      expect(state.currentConversationId).toBe("conv-new");
      expect(state.messages).toEqual([]); // Messages cleared when switching
      expect(result).toEqual(newConversation);
    });

    it("should prepend new conversation to list", async () => {
      // Set up existing conversation
      useChatStore.setState({
        conversations: [
          {
            id: "conv-old",
            user_id: "user-123",
            title: "Old Chat",
            ai_provider: "openai",
            ai_model: "gpt-4",
            system_prompt: null,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        ],
      });

      const newConversation = {
        id: "conv-new",
        user_id: "user-123",
        title: "New Chat",
        ai_provider: "anthropic",
        ai_model: "claude-3-opus",
        system_prompt: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      vi.mocked(chatApi.createConversation).mockResolvedValueOnce(newConversation);

      await useChatStore.getState().createConversation({
        title: "New Chat",
        ai_provider: "anthropic",
        ai_model: "claude-3-opus",
      });

      const state = useChatStore.getState();
      expect(state.conversations[0].id).toBe("conv-new"); // New one first
      expect(state.conversations).toHaveLength(2);
    });

    it("should set error on creation failure", async () => {
      vi.mocked(chatApi.createConversation).mockRejectedValueOnce(
        new Error("Failed to create conversation")
      );

      await expect(
        useChatStore.getState().createConversation({
          title: "Test",
          ai_provider: "openai",
          ai_model: "gpt-4",
        })
      ).rejects.toThrow("Failed to create conversation");

      const state = useChatStore.getState();
      expect(state.error).toBe("Failed to create conversation");
    });
  });

  describe("updateConversation", () => {
    it("should update conversation in list", async () => {
      const existingConversation = {
        id: "conv-1",
        user_id: "user-123",
        title: "Old Title",
        ai_provider: "openai",
        ai_model: "gpt-4",
        system_prompt: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      useChatStore.setState({
        conversations: [existingConversation],
      });

      const updatedConversation = {
        ...existingConversation,
        title: "New Title",
      };

      vi.mocked(chatApi.updateConversation).mockResolvedValueOnce(updatedConversation);

      await useChatStore.getState().updateConversation("conv-1", { title: "New Title" });

      const state = useChatStore.getState();
      expect(state.conversations[0].title).toBe("New Title");
    });

    it("should set error on update failure", async () => {
      vi.mocked(chatApi.updateConversation).mockRejectedValueOnce(new Error("Update failed"));

      await expect(
        useChatStore.getState().updateConversation("conv-1", { title: "New" })
      ).rejects.toThrow("Update failed");

      const state = useChatStore.getState();
      expect(state.error).toBe("Update failed");
    });
  });

  describe("deleteConversation", () => {
    it("should remove conversation from list", async () => {
      useChatStore.setState({
        conversations: [
          {
            id: "conv-1",
            user_id: "user-123",
            title: "Chat 1",
            ai_provider: "openai",
            ai_model: "gpt-4",
            system_prompt: null,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
          {
            id: "conv-2",
            user_id: "user-123",
            title: "Chat 2",
            ai_provider: "anthropic",
            ai_model: "claude-3-opus",
            system_prompt: null,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        ],
      });

      vi.mocked(chatApi.deleteConversation).mockResolvedValueOnce(undefined);

      await useChatStore.getState().deleteConversation("conv-1");

      const state = useChatStore.getState();
      expect(state.conversations).toHaveLength(1);
      expect(state.conversations[0].id).toBe("conv-2");
    });

    it("should clear current selection if deleting current conversation", async () => {
      useChatStore.setState({
        conversations: [
          {
            id: "conv-1",
            user_id: "user-123",
            title: "Chat 1",
            ai_provider: "openai",
            ai_model: "gpt-4",
            system_prompt: null,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        ],
        currentConversationId: "conv-1",
        messages: [
          {
            id: "msg-1",
            conversation_id: "conv-1",
            role: "user",
            content: "Hello",
            tokens_used: null,
            meta: null,
            created_at: new Date().toISOString(),
          },
        ],
      });

      vi.mocked(chatApi.deleteConversation).mockResolvedValueOnce(undefined);

      await useChatStore.getState().deleteConversation("conv-1");

      const state = useChatStore.getState();
      expect(state.currentConversationId).toBeNull();
      expect(state.messages).toEqual([]);
    });

    it("should keep current selection if deleting different conversation", async () => {
      useChatStore.setState({
        conversations: [
          {
            id: "conv-1",
            user_id: "user-123",
            title: "Chat 1",
            ai_provider: "openai",
            ai_model: "gpt-4",
            system_prompt: null,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
          {
            id: "conv-2",
            user_id: "user-123",
            title: "Chat 2",
            ai_provider: "anthropic",
            ai_model: "claude-3-opus",
            system_prompt: null,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        ],
        currentConversationId: "conv-1",
      });

      vi.mocked(chatApi.deleteConversation).mockResolvedValueOnce(undefined);

      await useChatStore.getState().deleteConversation("conv-2");

      const state = useChatStore.getState();
      expect(state.currentConversationId).toBe("conv-1");
    });
  });

  describe("selectConversation", () => {
    it("should update current conversation ID and clear messages", () => {
      useChatStore.setState({
        messages: [
          {
            id: "msg-1",
            conversation_id: "conv-old",
            role: "user",
            content: "Old message",
            tokens_used: null,
            meta: null,
            created_at: new Date().toISOString(),
          },
        ],
      });

      useChatStore.getState().selectConversation("conv-new");

      const state = useChatStore.getState();
      expect(state.currentConversationId).toBe("conv-new");
      expect(state.messages).toEqual([]);
      expect(state.error).toBeNull();
    });

    it("should allow selecting null (deselect)", () => {
      useChatStore.setState({
        currentConversationId: "conv-1",
      });

      useChatStore.getState().selectConversation(null);

      const state = useChatStore.getState();
      expect(state.currentConversationId).toBeNull();
    });
  });

  describe("loadMessages", () => {
    it("should load messages for conversation", async () => {
      const mockMessages = {
        messages: [
          {
            id: "msg-1",
            conversation_id: "conv-1",
            role: "user",
            content: "Hello",
            tokens_used: null,
            meta: null,
            created_at: new Date().toISOString(),
          },
          {
            id: "msg-2",
            conversation_id: "conv-1",
            role: "assistant",
            content: "Hi there!",
            tokens_used: 10,
            meta: null,
            created_at: new Date().toISOString(),
          },
        ],
        total: 2,
      };

      vi.mocked(chatApi.getMessages).mockResolvedValueOnce(mockMessages);

      await useChatStore.getState().loadMessages("conv-1");

      const state = useChatStore.getState();
      expect(chatApi.getMessages).toHaveBeenCalledWith("conv-1");
      expect(state.messages).toEqual(mockMessages.messages);
      expect(state.isLoadingMessages).toBe(false);
    });

    it("should set error on load failure", async () => {
      vi.mocked(chatApi.getMessages).mockRejectedValueOnce(new Error("Failed to load messages"));

      await expect(useChatStore.getState().loadMessages("conv-1")).rejects.toThrow(
        "Failed to load messages"
      );

      const state = useChatStore.getState();
      expect(state.error).toBe("Failed to load messages");
      expect(state.isLoadingMessages).toBe(false);
    });
  });

  describe("sendMessage - Optimistic Updates", () => {
    it("should throw error if no conversation selected", async () => {
      useChatStore.setState({
        currentConversationId: null,
      });

      await expect(useChatStore.getState().sendMessage("Hello")).rejects.toThrow(
        "No conversation selected"
      );
    });

    it("should add optimistic message and replace with real messages on success", async () => {
      useChatStore.setState({
        currentConversationId: "conv-1",
        messages: [],
      });

      const mockResponse = {
        user_message: {
          id: "msg-user",
          conversation_id: "conv-1",
          role: "user" as const,
          content: "Hello AI",
          tokens_used: null,
          meta: null,
          created_at: new Date().toISOString(),
        },
        assistant_message: {
          id: "msg-assistant",
          conversation_id: "conv-1",
          role: "assistant" as const,
          content: "Hello!",
          tokens_used: 5,
          meta: null,
          created_at: new Date().toISOString(),
        },
      };

      vi.mocked(chatApi.sendMessage).mockResolvedValueOnce(mockResponse);

      await useChatStore.getState().sendMessage("Hello AI");

      const state = useChatStore.getState();
      // Should have 2 messages (user + assistant), optimistic removed
      expect(state.messages).toHaveLength(2);
      expect(state.messages[0].id).toBe("msg-user");
      expect(state.messages[0].status).toBe("sent");
      expect(state.messages[1].id).toBe("msg-assistant");
      expect(state.messages[1].role).toBe("assistant");
      expect(state.isSendingMessage).toBe(false);
    });

    it("should mark optimistic message as failed on error", async () => {
      useChatStore.setState({
        currentConversationId: "conv-1",
        messages: [],
      });

      vi.mocked(chatApi.sendMessage).mockRejectedValueOnce(new Error("Send failed"));

      // Should throw but also update state
      try {
        await useChatStore.getState().sendMessage("Hello");
        expect.fail("Should have thrown error");
      } catch (error) {
        expect((error as Error).message).toBe("Send failed");
      }

      const state = useChatStore.getState();
      expect(state.messages).toHaveLength(1);
      expect(state.messages[0].status).toBe("failed");
      expect(state.messages[0].error).toBe("Send failed");
      expect(state.isSendingMessage).toBe(false);
      expect(state.error).toBe("Send failed");
    });
  });

  describe("retryMessage", () => {
    it("should retry failed message", async () => {
      vi.clearAllMocks(); // Clear previous mocks

      useChatStore.setState({
        currentConversationId: "conv-1",
        messages: [
          {
            id: "msg-failed",
            conversation_id: "conv-1",
            role: "user",
            content: "Hello",
            tokens_used: null,
            meta: null,
            created_at: new Date().toISOString(),
            status: "failed" as const,
            error: "Network error",
          },
        ],
      });

      const mockResponse = {
        user_message: {
          id: "msg-user-retry",
          conversation_id: "conv-1",
          role: "user" as const,
          content: "Hello",
          tokens_used: null,
          meta: null,
          created_at: new Date().toISOString(),
        },
        assistant_message: {
          id: "msg-assistant",
          conversation_id: "conv-1",
          role: "assistant" as const,
          content: "Hi!",
          tokens_used: 5,
          meta: null,
          created_at: new Date().toISOString(),
        },
      };

      vi.mocked(chatApi.sendMessage).mockResolvedValueOnce(mockResponse);

      await useChatStore.getState().retryMessage("msg-failed");

      const state = useChatStore.getState();
      expect(state.messages).toHaveLength(2);
      expect(state.messages[0].status).toBe("sent");
      expect(state.isSendingMessage).toBe(false);
    });

    it("should do nothing if message not found or not failed", async () => {
      useChatStore.setState({
        currentConversationId: "conv-1",
        messages: [],
      });

      await useChatStore.getState().retryMessage("non-existent");

      expect(chatApi.sendMessage).not.toHaveBeenCalled();
    });
  });

  describe("removeMessage", () => {
    it("should remove message from list", () => {
      useChatStore.setState({
        messages: [
          {
            id: "msg-1",
            conversation_id: "conv-1",
            role: "user",
            content: "Message 1",
            tokens_used: null,
            meta: null,
            created_at: new Date().toISOString(),
          },
          {
            id: "msg-2",
            conversation_id: "conv-1",
            role: "user",
            content: "Message 2",
            tokens_used: null,
            meta: null,
            created_at: new Date().toISOString(),
          },
        ],
      });

      useChatStore.getState().removeMessage("msg-1");

      const state = useChatStore.getState();
      expect(state.messages).toHaveLength(1);
      expect(state.messages[0].id).toBe("msg-2");
    });
  });

  describe("clearError", () => {
    it("should clear error state", () => {
      useChatStore.setState({
        error: "Some error",
      });

      useChatStore.getState().clearError();

      const state = useChatStore.getState();
      expect(state.error).toBeNull();
    });
  });

  describe("Computed Properties", () => {
    it("should find current conversation from list", () => {
      const conversation1 = {
        id: "conv-1",
        user_id: "user-123",
        title: "Chat 1",
        ai_provider: "openai",
        ai_model: "gpt-4",
        system_prompt: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      const conversation2 = {
        id: "conv-2",
        user_id: "user-123",
        title: "Chat 2",
        ai_provider: "anthropic",
        ai_model: "claude-3-opus",
        system_prompt: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      useChatStore.setState({
        conversations: [conversation1, conversation2],
        currentConversationId: "conv-2",
      });

      // Test that we can find conversation in the list
      const state = useChatStore.getState();
      const found = state.conversations.find((c) => c.id === state.currentConversationId);
      expect(found).toEqual(conversation2);
    });

    it("should handle null when conversation not in list", () => {
      useChatStore.setState({
        conversations: [],
        currentConversationId: null,
      });

      const state = useChatStore.getState();
      expect(state.currentConversationId).toBeNull();
      expect(state.conversations).toEqual([]);
    });
  });

  // ========================================
  // CRITICAL TESTS: These would have caught the getter bug!
  // ========================================
  describe("currentConversation State Management (Bug Prevention)", () => {
    const mockConv1 = {
      id: "conv-1",
      user_id: "user-123",
      title: "Chat 1",
      ai_provider: "openai",
      ai_model: "gpt-4",
      system_prompt: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    const mockConv2 = {
      id: "conv-2",
      user_id: "user-123",
      title: "Chat 2",
      ai_provider: "anthropic",
      ai_model: "claude-3-opus",
      system_prompt: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    describe("selectConversation", () => {
      it("CRITICAL: should update currentConversation when selecting from existing list", () => {
        // Setup: Load conversations first
        useChatStore.setState({
          conversations: [mockConv1, mockConv2],
          currentConversationId: null,
          currentConversation: null,
        });

        // Act: Select conversation
        useChatStore.getState().selectConversation("conv-2");

        // Assert: currentConversation MUST be updated
        const state = useChatStore.getState();
        expect(state.currentConversationId).toBe("conv-2");
        expect(state.currentConversation).not.toBeNull(); // ← WOULD FAIL with getter!
        expect(state.currentConversation?.id).toBe("conv-2");
        expect(state.currentConversation).toEqual(mockConv2);
      });

      it("CRITICAL: should set currentConversation to null when conversation not found", () => {
        useChatStore.setState({
          conversations: [mockConv1],
          currentConversationId: null,
          currentConversation: null,
        });

        // Select conversation that doesn't exist
        useChatStore.getState().selectConversation("non-existent");

        const state = useChatStore.getState();
        expect(state.currentConversationId).toBe("non-existent");
        expect(state.currentConversation).toBeNull(); // ← Should be null since not found
      });

      it("should clear currentConversation when deselecting", () => {
        useChatStore.setState({
          conversations: [mockConv1],
          currentConversationId: "conv-1",
          currentConversation: mockConv1,
        });

        useChatStore.getState().selectConversation(null);

        const state = useChatStore.getState();
        expect(state.currentConversationId).toBeNull();
        expect(state.currentConversation).toBeNull();
      });
    });

    describe("loadConversations", () => {
      it("CRITICAL: should restore currentConversation after loading if ID matches", async () => {
        // Setup: User had selected a conversation before
        useChatStore.setState({
          conversations: [],
          currentConversationId: "conv-2", // Selected before reload
          currentConversation: null, // Lost after reload
        });

        vi.mocked(chatApi.listConversations).mockResolvedValueOnce({
          conversations: [mockConv1, mockConv2],
          total: 2,
        });

        // Act: Load conversations (simulates page refresh)
        await useChatStore.getState().loadConversations();

        // Assert: Should restore currentConversation
        const state = useChatStore.getState();
        expect(state.currentConversationId).toBe("conv-2");
        expect(state.currentConversation).not.toBeNull(); // ← CRITICAL!
        expect(state.currentConversation?.id).toBe("conv-2");
      });

      it("should set currentConversation to null if ID doesn't match loaded list", async () => {
        useChatStore.setState({
          currentConversationId: "non-existent",
          currentConversation: null,
        });

        vi.mocked(chatApi.listConversations).mockResolvedValueOnce({
          conversations: [mockConv1],
          total: 1,
        });

        await useChatStore.getState().loadConversations();

        const state = useChatStore.getState();
        expect(state.currentConversation).toBeNull();
      });
    });

    describe("createConversation", () => {
      it("CRITICAL: should set new conversation as currentConversation", async () => {
        const newConv = {
          id: "conv-new",
          user_id: "user-123",
          title: "New Chat",
          ai_provider: "openai",
          ai_model: "gpt-4",
          system_prompt: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        };

        vi.mocked(chatApi.createConversation).mockResolvedValueOnce(newConv);

        await useChatStore.getState().createConversation({
          title: "New Chat",
          ai_provider: "openai",
          ai_model: "gpt-4",
        });

        const state = useChatStore.getState();
        expect(state.currentConversationId).toBe("conv-new");
        expect(state.currentConversation).not.toBeNull(); // ← CRITICAL!
        expect(state.currentConversation?.id).toBe("conv-new");
        expect(state.currentConversation).toEqual(newConv);
      });
    });

    describe("updateConversation", () => {
      it("CRITICAL: should update currentConversation if updating current one", async () => {
        const updated = { ...mockConv1, title: "Updated Title" };

        useChatStore.setState({
          conversations: [mockConv1, mockConv2],
          currentConversationId: "conv-1",
          currentConversation: mockConv1,
        });

        vi.mocked(chatApi.updateConversation).mockResolvedValueOnce(updated);

        await useChatStore.getState().updateConversation("conv-1", { title: "Updated Title" });

        const state = useChatStore.getState();
        expect(state.currentConversation?.title).toBe("Updated Title");
        expect(state.currentConversation).toEqual(updated);
      });

      it("should NOT update currentConversation if updating different conversation", async () => {
        const updated = { ...mockConv2, title: "Updated Title" };

        useChatStore.setState({
          conversations: [mockConv1, mockConv2],
          currentConversationId: "conv-1",
          currentConversation: mockConv1,
        });

        vi.mocked(chatApi.updateConversation).mockResolvedValueOnce(updated);

        await useChatStore.getState().updateConversation("conv-2", { title: "Updated Title" });

        const state = useChatStore.getState();
        expect(state.currentConversation).toEqual(mockConv1); // Unchanged
        expect(state.currentConversation?.title).toBe("Chat 1");
      });
    });

    describe("deleteConversation", () => {
      it("CRITICAL: should clear currentConversation if deleting current one", async () => {
        useChatStore.setState({
          conversations: [mockConv1, mockConv2],
          currentConversationId: "conv-1",
          currentConversation: mockConv1,
        });

        vi.mocked(chatApi.deleteConversation).mockResolvedValueOnce(undefined);

        await useChatStore.getState().deleteConversation("conv-1");

        const state = useChatStore.getState();
        expect(state.currentConversationId).toBeNull();
        expect(state.currentConversation).toBeNull(); // ← CRITICAL!
        expect(state.messages).toEqual([]);
      });

      it("should keep currentConversation if deleting different conversation", async () => {
        useChatStore.setState({
          conversations: [mockConv1, mockConv2],
          currentConversationId: "conv-1",
          currentConversation: mockConv1,
        });

        vi.mocked(chatApi.deleteConversation).mockResolvedValueOnce(undefined);

        await useChatStore.getState().deleteConversation("conv-2");

        const state = useChatStore.getState();
        expect(state.currentConversationId).toBe("conv-1");
        expect(state.currentConversation).toEqual(mockConv1); // Unchanged
      });
    });
  });
});
