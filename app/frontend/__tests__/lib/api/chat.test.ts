/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, it, expect, beforeEach, vi } from "vitest";
import * as chatApi from "@/lib/api/chat";
import { authenticatedClient } from "@/lib/api-client";

/**
 * ✨ CRITICAL TESTS ✨
 *
 * These tests prevent the bug that occurred where NewConversationModal
 * was calling fetch() directly instead of using authenticatedClient,
 * resulting in 403 errors.
 *
 * Every chat API function MUST use authenticatedClient to ensure
 * the JWT token is included in requests.
 */

// Mock the authenticated client
vi.mock("@/lib/api-client", () => ({
  authenticatedClient: {
    GET: vi.fn(),
    POST: vi.fn(),
    PATCH: vi.fn(),
    DELETE: vi.fn(),
  },
  apiClient: {
    POST: vi.fn(),
  },
  setAuthToken: vi.fn(),
  clearAuthToken: vi.fn(),
  setRefreshTokenCallback: vi.fn(),
}));

describe("Chat API Functions - Authentication Guard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("listProviders ✨ PREVENTS THE BUG THAT OCCURRED", () => {
    it("MUST use authenticatedClient (not fetch or apiClient)", async () => {
      const mockProviders = {
        providers: [
          {
            id: "openai",
            label: "OpenAI",
            models: [{ value: "gpt-4", label: "GPT-4" }],
            is_configured: true,
          },
        ],
      };

      vi.mocked(authenticatedClient.GET).mockResolvedValueOnce({
        data: mockProviders,
        error: undefined,
      } as any);

      const result = await chatApi.listProviders();

      // ✅ THIS IS THE CRITICAL CHECK
      expect(authenticatedClient.GET).toHaveBeenCalledWith("/chat/providers");
      expect(result).toEqual(mockProviders);
    });

    it("should throw error if request fails (401 Forbidden)", async () => {
      vi.mocked(authenticatedClient.GET).mockResolvedValueOnce({
        data: undefined,
        error: { detail: "Not authenticated" },
      } as any);

      await expect(chatApi.listProviders()).rejects.toThrow();
    });

    it("should handle empty provider list", async () => {
      vi.mocked(authenticatedClient.GET).mockResolvedValueOnce({
        data: { providers: [] },
        error: undefined,
      } as any);

      const result = await chatApi.listProviders();

      expect(result.providers).toEqual([]);
    });
  });

  describe("createConversation", () => {
    it("MUST use authenticatedClient", async () => {
      const mockConversation = {
        id: "conv-123",
        user_id: "user-123",
        title: "Test Chat",
        ai_provider: "openai",
        ai_model: "gpt-4",
        system_prompt: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      vi.mocked(authenticatedClient.POST).mockResolvedValueOnce({
        data: mockConversation,
        error: undefined,
      } as any);

      const createData = {
        title: "Test Chat",
        ai_provider: "openai",
        ai_model: "gpt-4",
      };

      const result = await chatApi.createConversation(createData);

      expect(authenticatedClient.POST).toHaveBeenCalledWith("/chat/conversations", {
        body: createData,
      });
      expect(result).toEqual(mockConversation);
    });

    it("should throw error on validation failure", async () => {
      vi.mocked(authenticatedClient.POST).mockResolvedValueOnce({
        data: undefined,
        error: { detail: "Title is required" },
      } as any);

      await expect(
        chatApi.createConversation({
          title: "",
          ai_provider: "openai",
          ai_model: "gpt-4",
        })
      ).rejects.toThrow();
    });
  });

  describe("listConversations", () => {
    it("MUST use authenticatedClient", async () => {
      const mockResponse = {
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
        total: 1,
      };

      vi.mocked(authenticatedClient.GET).mockResolvedValueOnce({
        data: mockResponse,
        error: undefined,
      } as any);

      const result = await chatApi.listConversations();

      expect(authenticatedClient.GET).toHaveBeenCalledWith("/chat/conversations");
      expect(result).toEqual(mockResponse);
    });

    it("should return empty list for new users", async () => {
      vi.mocked(authenticatedClient.GET).mockResolvedValueOnce({
        data: { conversations: [], total: 0 },
        error: undefined,
      } as any);

      const result = await chatApi.listConversations();

      expect(result.conversations).toEqual([]);
      expect(result.total).toBe(0);
    });
  });

  describe("getConversation", () => {
    it("MUST use authenticatedClient", async () => {
      const mockConversation = {
        id: "conv-123",
        user_id: "user-123",
        title: "Test Chat",
        ai_provider: "openai",
        ai_model: "gpt-4",
        system_prompt: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      vi.mocked(authenticatedClient.GET).mockResolvedValueOnce({
        data: mockConversation,
        error: undefined,
      } as any);

      const result = await chatApi.getConversation("conv-123");

      expect(authenticatedClient.GET).toHaveBeenCalledWith(
        "/chat/conversations/{conversation_id}",
        {
          params: {
            path: {
              conversation_id: "conv-123",
            },
          },
        }
      );
      expect(result).toEqual(mockConversation);
    });

    it("should throw 404 for non-existent conversation", async () => {
      vi.mocked(authenticatedClient.GET).mockResolvedValueOnce({
        data: undefined,
        error: { detail: "Conversation not found" },
      } as any);

      await expect(chatApi.getConversation("invalid-id")).rejects.toThrow();
    });
  });

  describe("updateConversation", () => {
    it("MUST use authenticatedClient", async () => {
      const mockUpdated = {
        id: "conv-123",
        user_id: "user-123",
        title: "Updated Title",
        ai_provider: "openai",
        ai_model: "gpt-4",
        system_prompt: "You are a helpful assistant",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      vi.mocked(authenticatedClient.PATCH).mockResolvedValueOnce({
        data: mockUpdated,
        error: undefined,
      } as any);

      const updateData = {
        title: "Updated Title",
        system_prompt: "You are a helpful assistant",
      };

      const result = await chatApi.updateConversation("conv-123", updateData);

      expect(authenticatedClient.PATCH).toHaveBeenCalledWith(
        "/chat/conversations/{conversation_id}",
        {
          params: {
            path: {
              conversation_id: "conv-123",
            },
          },
          body: updateData,
        }
      );
      expect(result).toEqual(mockUpdated);
    });
  });

  describe("deleteConversation", () => {
    it("MUST use authenticatedClient", async () => {
      vi.mocked(authenticatedClient.DELETE).mockResolvedValueOnce({
        data: undefined,
        error: undefined,
      } as any);

      await chatApi.deleteConversation("conv-123");

      expect(authenticatedClient.DELETE).toHaveBeenCalledWith(
        "/chat/conversations/{conversation_id}",
        {
          params: {
            path: {
              conversation_id: "conv-123",
            },
          },
        }
      );
    });

    it("should throw error if user doesn't own conversation", async () => {
      vi.mocked(authenticatedClient.DELETE).mockResolvedValueOnce({
        data: undefined,
        error: { detail: "Forbidden" },
      } as any);

      await expect(chatApi.deleteConversation("other-user-conv")).rejects.toThrow();
    });
  });

  describe("getMessages", () => {
    it("MUST use authenticatedClient", async () => {
      const mockMessages = {
        messages: [
          {
            id: "msg-1",
            conversation_id: "conv-123",
            role: "user",
            content: "Hello",
            tokens_used: null,
            meta: null,
            created_at: new Date().toISOString(),
          },
        ],
        total: 1,
      };

      vi.mocked(authenticatedClient.GET).mockResolvedValueOnce({
        data: mockMessages,
        error: undefined,
      } as any);

      const result = await chatApi.getMessages("conv-123");

      expect(authenticatedClient.GET).toHaveBeenCalledWith(
        "/chat/conversations/{conversation_id}/messages",
        {
          params: {
            path: {
              conversation_id: "conv-123",
            },
          },
        }
      );
      expect(result).toEqual(mockMessages);
    });
  });

  describe("sendMessage", () => {
    it("MUST use authenticatedClient", async () => {
      const mockResponse = {
        user_message: {
          id: "msg-user",
          conversation_id: "conv-123",
          role: "user",
          content: "Hello AI",
          tokens_used: null,
          meta: null,
          created_at: new Date().toISOString(),
        },
        assistant_message: {
          id: "msg-assistant",
          conversation_id: "conv-123",
          role: "assistant",
          content: "Hello! How can I help?",
          tokens_used: 15,
          meta: null,
          created_at: new Date().toISOString(),
        },
      };

      vi.mocked(authenticatedClient.POST).mockResolvedValueOnce({
        data: mockResponse,
        error: undefined,
      } as any);

      const messageData = {
        role: "user" as const,
        content: "Hello AI",
      };

      const result = await chatApi.sendMessage("conv-123", messageData);

      expect(authenticatedClient.POST).toHaveBeenCalledWith(
        "/chat/conversations/{conversation_id}/messages",
        {
          params: {
            path: {
              conversation_id: "conv-123",
            },
          },
          body: messageData,
        }
      );
      expect(result).toEqual(mockResponse);
    });

    it("should throw error if conversation not found", async () => {
      vi.mocked(authenticatedClient.POST).mockResolvedValueOnce({
        data: undefined,
        error: { detail: "Conversation not found" },
      } as any);

      await expect(
        chatApi.sendMessage("invalid-conv", {
          role: "user",
          content: "Hello",
        })
      ).rejects.toThrow();
    });
  });

  describe("Error Handling - All Functions", () => {
    it("should format error messages consistently", async () => {
      const errorCases = [{ detail: "Simple error" }, { detail: [{ msg: "Validation error" }] }];

      for (const error of errorCases) {
        vi.mocked(authenticatedClient.GET).mockResolvedValueOnce({
          data: undefined,
          error,
        } as any);

        await expect(chatApi.listProviders()).rejects.toThrow();
      }
    });

    it("should handle network errors gracefully", async () => {
      vi.mocked(authenticatedClient.GET).mockRejectedValueOnce(new Error("Network error"));

      await expect(chatApi.listProviders()).rejects.toThrow("Network error");
    });
  });

  describe("Integration - Authorization Guard", () => {
    it("ALL chat functions require authentication", async () => {
      // Mock 401 Unauthorized for all calls
      const unauthorizedError = { detail: "Not authenticated" };

      vi.mocked(authenticatedClient.GET).mockResolvedValue({
        data: undefined,
        error: unauthorizedError,
      } as any);

      vi.mocked(authenticatedClient.POST).mockResolvedValue({
        data: undefined,
        error: unauthorizedError,
      } as any);

      vi.mocked(authenticatedClient.PATCH).mockResolvedValue({
        data: undefined,
        error: unauthorizedError,
      } as any);

      vi.mocked(authenticatedClient.DELETE).mockResolvedValue({
        data: undefined,
        error: unauthorizedError,
      } as any);

      // All should fail with authentication error
      await expect(chatApi.listProviders()).rejects.toThrow();
      await expect(chatApi.listConversations()).rejects.toThrow();
      await expect(chatApi.getConversation("id")).rejects.toThrow();
      await expect(
        chatApi.createConversation({ title: "test", ai_provider: "openai", ai_model: "gpt-4" })
      ).rejects.toThrow();
      await expect(chatApi.updateConversation("id", { title: "new" })).rejects.toThrow();
      await expect(chatApi.deleteConversation("id")).rejects.toThrow();
      await expect(chatApi.getMessages("id")).rejects.toThrow();
      await expect(chatApi.sendMessage("id", { role: "user", content: "test" })).rejects.toThrow();
    });
  });
});
