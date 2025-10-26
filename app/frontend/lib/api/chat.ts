import { authenticatedClient } from "@/lib/api-client";
import type { components } from "@/types/api";

// Type aliases for cleaner code
type ConversationCreate = components["schemas"]["ConversationCreate"];
type ConversationUpdate = components["schemas"]["ConversationUpdate"];
type ConversationRead = components["schemas"]["ConversationRead"];
type ConversationList = components["schemas"]["ConversationList"];
type MessageCreate = components["schemas"]["MessageCreate"];
type MessageList = components["schemas"]["MessageList"];
type MessageCreateResponse = components["schemas"]["MessageCreateResponse"];
type AIProviderList = components["schemas"]["AIProviderList"];

/**
 * Helper to format error messages from API responses
 */
function formatErrorMessage(error: unknown, fallback: string): string {
  if (!error) return fallback;

  // Handle validation errors (array of errors)
  if (Array.isArray(error)) {
    return error.map((e) => e.msg || "Unknown error").join(", ");
  }

  // Handle string errors
  if (typeof error === "string") {
    return error;
  }

  return fallback;
}

/**
 * Create a new conversation
 */
export async function createConversation(data: ConversationCreate): Promise<ConversationRead> {
  const response = await authenticatedClient.POST("/chat/conversations", {
    body: data,
  });

  if (response.error) {
    throw new Error(formatErrorMessage(response.error.detail, "Failed to create conversation"));
  }

  return response.data;
}

/**
 * List all conversations for the current user
 */
export async function listConversations(): Promise<ConversationList> {
  const response = await authenticatedClient.GET("/chat/conversations");

  if (response.error) {
    throw new Error("Failed to list conversations");
  }

  return response.data;
}

/**
 * Get a conversation by ID
 */
export async function getConversation(conversationId: string): Promise<ConversationRead> {
  const response = await authenticatedClient.GET("/chat/conversations/{conversation_id}", {
    params: {
      path: {
        conversation_id: conversationId,
      },
    },
  });

  if (response.error) {
    throw new Error(formatErrorMessage(response.error.detail, "Failed to get conversation"));
  }

  return response.data;
}

/**
 * Update a conversation
 */
export async function updateConversation(
  conversationId: string,
  data: ConversationUpdate
): Promise<ConversationRead> {
  const response = await authenticatedClient.PATCH("/chat/conversations/{conversation_id}", {
    params: {
      path: {
        conversation_id: conversationId,
      },
    },
    body: data,
  });

  if (response.error) {
    throw new Error(formatErrorMessage(response.error.detail, "Failed to update conversation"));
  }

  return response.data;
}

/**
 * Delete a conversation
 */
export async function deleteConversation(conversationId: string): Promise<void> {
  const response = await authenticatedClient.DELETE("/chat/conversations/{conversation_id}", {
    params: {
      path: {
        conversation_id: conversationId,
      },
    },
  });

  if (response.error) {
    throw new Error(formatErrorMessage(response.error.detail, "Failed to delete conversation"));
  }
}

/**
 * Get all messages in a conversation
 */
export async function getMessages(conversationId: string): Promise<MessageList> {
  const response = await authenticatedClient.GET("/chat/conversations/{conversation_id}/messages", {
    params: {
      path: {
        conversation_id: conversationId,
      },
    },
  });

  if (response.error) {
    throw new Error(formatErrorMessage(response.error.detail, "Failed to get messages"));
  }

  return response.data;
}

/**
 * Send a message in a conversation
 */
export async function sendMessage(
  conversationId: string,
  data: MessageCreate
): Promise<MessageCreateResponse> {
  const response = await authenticatedClient.POST(
    "/chat/conversations/{conversation_id}/messages",
    {
      params: {
        path: {
          conversation_id: conversationId,
        },
      },
      body: data,
    }
  );

  if (response.error) {
    throw new Error(formatErrorMessage(response.error.detail, "Failed to send message"));
  }

  return response.data;
}

/**
 * List all available AI providers
 */
export async function listProviders(): Promise<AIProviderList> {
  const response = await authenticatedClient.GET("/chat/providers");

  // Note: This endpoint only returns 200 responses according to OpenAPI spec
  if (!response.data) {
    throw new Error("Failed to list providers");
  }

  return response.data;
}
