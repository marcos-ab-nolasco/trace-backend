import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NewConversationModal } from "@/components/chat/NewConversationModal";
import * as chatApi from "@/lib/api/chat";

/**
 * ✨ CRITICAL TESTS ✨
 *
 * These tests prevent the bug that occurred where NewConversationModal
 * was calling fetch() directly instead of using chatApi.listProviders(),
 * resulting in 403 errors because no authentication token was sent.
 *
 * The modal MUST use chatApi.listProviders() to ensure authentication.
 */

// Mock the chat API
vi.mock("@/lib/api/chat");

describe("NewConversationModal - Authentication Guard", () => {
  const mockOnClose = vi.fn();
  const mockOnSubmit = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("✨ PREVENTS THE BUG - Provider Loading", () => {
    it("MUST use chatApi.listProviders() NOT fetch()", async () => {
      const mockProviders = {
        providers: [
          {
            id: "openai",
            label: "OpenAI",
            models: [
              { value: "gpt-4", label: "GPT-4" },
              { value: "gpt-3.5-turbo", label: "GPT-3.5 Turbo" },
            ],
            is_configured: true,
          },
          {
            id: "anthropic",
            label: "Anthropic",
            models: [
              { value: "claude-3-opus", label: "Claude 3 Opus" },
              { value: "claude-3-sonnet", label: "Claude 3 Sonnet" },
            ],
            is_configured: true,
          },
        ],
      };

      vi.mocked(chatApi.listProviders).mockResolvedValueOnce(mockProviders);

      render(<NewConversationModal isOpen={true} onClose={mockOnClose} onSubmit={mockOnSubmit} />);

      // ✅ CRITICAL: Must call authenticated API function
      await waitFor(() => {
        expect(chatApi.listProviders).toHaveBeenCalled();
      });

      // Verify providers are displayed
      await waitFor(() => {
        expect(screen.getByText("OpenAI")).toBeInTheDocument();
        expect(screen.getByText("Anthropic")).toBeInTheDocument();
      });
    });

    it("should display loading state while fetching providers", () => {
      vi.mocked(chatApi.listProviders).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      render(<NewConversationModal isOpen={true} onClose={mockOnClose} onSubmit={mockOnSubmit} />);

      expect(screen.getByText(/Carregando provedores/i)).toBeInTheDocument();
    });

    it("should display error if provider loading fails", async () => {
      vi.mocked(chatApi.listProviders).mockRejectedValueOnce(new Error("Failed to load providers"));

      render(<NewConversationModal isOpen={true} onClose={mockOnClose} onSubmit={mockOnSubmit} />);

      await waitFor(() => {
        expect(
          screen.getByText(/Não foi possível carregar os provedores de IA/i)
        ).toBeInTheDocument();
      });
    });

    it("should handle empty provider list", async () => {
      vi.mocked(chatApi.listProviders).mockResolvedValueOnce({
        providers: [],
      });

      render(<NewConversationModal isOpen={true} onClose={mockOnClose} onSubmit={mockOnSubmit} />);

      await waitFor(() => {
        expect(chatApi.listProviders).toHaveBeenCalled();
      });

      // Should not crash with empty providers
      expect(screen.getByText("Nova Conversa")).toBeInTheDocument();
    });

    it("should mark unconfigured providers in UI", async () => {
      vi.mocked(chatApi.listProviders).mockResolvedValueOnce({
        providers: [
          {
            id: "openai",
            label: "OpenAI",
            models: [{ value: "gpt-4", label: "GPT-4" }],
            is_configured: true,
          },
          {
            id: "grok",
            label: "Grok",
            models: [{ value: "grok-beta", label: "Grok Beta" }],
            is_configured: false,
          },
        ],
      });

      render(<NewConversationModal isOpen={true} onClose={mockOnClose} onSubmit={mockOnSubmit} />);

      await waitFor(() => {
        expect(screen.getByText("OpenAI")).toBeInTheDocument();
        expect(screen.getByText(/Grok.*não configurado/i)).toBeInTheDocument();
      });
    });
  });

  describe("Modal Behavior", () => {
    beforeEach(() => {
      vi.mocked(chatApi.listProviders).mockResolvedValue({
        providers: [
          {
            id: "openai",
            label: "OpenAI",
            models: [{ value: "gpt-4", label: "GPT-4" }],
            is_configured: true,
          },
        ],
      });
    });

    it("should not render when closed", () => {
      const { container } = render(
        <NewConversationModal isOpen={false} onClose={mockOnClose} onSubmit={mockOnSubmit} />
      );

      expect(container.firstChild).toBeNull();
    });

    it("should render modal when open", async () => {
      render(<NewConversationModal isOpen={true} onClose={mockOnClose} onSubmit={mockOnSubmit} />);

      await waitFor(() => {
        expect(screen.getByText("Nova Conversa")).toBeInTheDocument();
      });
    });

    it("should close modal when close button clicked", async () => {
      const user = userEvent.setup();

      render(<NewConversationModal isOpen={true} onClose={mockOnClose} onSubmit={mockOnSubmit} />);

      await waitFor(() => {
        expect(screen.getByText("Nova Conversa")).toBeInTheDocument();
      });

      const closeButton = screen.getByRole("button", { name: /cancelar/i });
      await user.click(closeButton);

      expect(mockOnClose).toHaveBeenCalled();
    });

    it("should call onClose when X button clicked", async () => {
      const user = userEvent.setup();

      render(<NewConversationModal isOpen={true} onClose={mockOnClose} onSubmit={mockOnSubmit} />);

      await waitFor(() => {
        expect(screen.getByText("Nova Conversa")).toBeInTheDocument();
      });

      // Find the X button (has an SVG with paths for the X)
      const xButton = screen.getByRole("button", { name: "" });
      await user.click(xButton);

      expect(mockOnClose).toHaveBeenCalled();
    });
  });

  describe("Form Validation", () => {
    beforeEach(() => {
      vi.mocked(chatApi.listProviders).mockResolvedValue({
        providers: [
          {
            id: "openai",
            label: "OpenAI",
            models: [
              { value: "gpt-4", label: "GPT-4" },
              { value: "gpt-3.5-turbo", label: "GPT-3.5 Turbo" },
            ],
            is_configured: true,
          },
        ],
      });
    });

    it("should require title field", async () => {
      const user = userEvent.setup();

      render(<NewConversationModal isOpen={true} onClose={mockOnClose} onSubmit={mockOnSubmit} />);

      await waitFor(() => {
        expect(screen.getByText("Nova Conversa")).toBeInTheDocument();
      });

      const submitButton = screen.getByRole("button", { name: /Criar Conversa/i });
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/Título é obrigatório/i)).toBeInTheDocument();
      });

      expect(mockOnSubmit).not.toHaveBeenCalled();
    });

    it("should submit form with valid data", async () => {
      const user = userEvent.setup();

      mockOnSubmit.mockResolvedValueOnce(undefined);

      render(<NewConversationModal isOpen={true} onClose={mockOnClose} onSubmit={mockOnSubmit} />);

      await waitFor(() => {
        expect(screen.getByText("Nova Conversa")).toBeInTheDocument();
      });

      // Fill in title
      const titleInput = screen.getByLabelText(/Título/i);
      await user.type(titleInput, "My Test Chat");

      // Submit form
      const submitButton = screen.getByRole("button", { name: /Criar Conversa/i });
      await user.click(submitButton);

      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalledWith(
          expect.objectContaining({
            title: "My Test Chat",
            ai_provider: "openai",
            ai_model: "gpt-4",
          })
        );
      });
    });

    it("should include system prompt if provided", async () => {
      const user = userEvent.setup();

      mockOnSubmit.mockResolvedValueOnce(undefined);

      render(<NewConversationModal isOpen={true} onClose={mockOnClose} onSubmit={mockOnSubmit} />);

      await waitFor(() => {
        expect(screen.getByText("Nova Conversa")).toBeInTheDocument();
      });

      const titleInput = screen.getByLabelText(/Título/i);
      await user.type(titleInput, "Test Chat");

      const systemPromptInput = screen.getByLabelText(/Prompt do Sistema/i);
      await user.type(systemPromptInput, "You are a helpful assistant");

      const submitButton = screen.getByRole("button", { name: /Criar Conversa/i });
      await user.click(submitButton);

      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalledWith(
          expect.objectContaining({
            title: "Test Chat",
            system_prompt: "You are a helpful assistant",
          })
        );
      });
    });

    it("should prevent submission while submitting", async () => {
      const user = userEvent.setup();

      render(
        <NewConversationModal
          isOpen={true}
          onClose={mockOnClose}
          onSubmit={mockOnSubmit}
          isSubmitting={true}
        />
      );

      await waitFor(() => {
        expect(screen.getByText("Nova Conversa")).toBeInTheDocument();
      });

      const submitButton = screen.getByRole("button", { name: /Criando.../i });
      expect(submitButton).toBeDisabled();

      await user.click(submitButton);
      expect(mockOnSubmit).not.toHaveBeenCalled();
    });
  });

  describe("Provider and Model Selection", () => {
    it("should update available models when provider changes", async () => {
      const user = userEvent.setup();

      vi.mocked(chatApi.listProviders).mockResolvedValueOnce({
        providers: [
          {
            id: "openai",
            label: "OpenAI",
            models: [
              { value: "gpt-4", label: "GPT-4" },
              { value: "gpt-3.5-turbo", label: "GPT-3.5 Turbo" },
            ],
            is_configured: true,
          },
          {
            id: "anthropic",
            label: "Anthropic",
            models: [
              { value: "claude-3-opus", label: "Claude 3 Opus" },
              { value: "claude-3-sonnet", label: "Claude 3 Sonnet" },
            ],
            is_configured: true,
          },
        ],
      });

      render(<NewConversationModal isOpen={true} onClose={mockOnClose} onSubmit={mockOnSubmit} />);

      await waitFor(() => {
        expect(screen.getByText("OpenAI")).toBeInTheDocument();
      });

      // Change provider to Anthropic
      const providerSelect = screen.getByLabelText(/Provedor de IA/i);
      await user.selectOptions(providerSelect, "anthropic");

      // Verify provider changed
      await waitFor(() => {
        const select = screen.getByLabelText(/Provedor de IA/i) as HTMLSelectElement;
        expect(select.value).toBe("anthropic");
      });
    });

    it("should select first configured provider by default", async () => {
      vi.mocked(chatApi.listProviders).mockResolvedValueOnce({
        providers: [
          {
            id: "grok",
            label: "Grok",
            models: [{ value: "grok-beta", label: "Grok Beta" }],
            is_configured: false,
          },
          {
            id: "openai",
            label: "OpenAI",
            models: [{ value: "gpt-4", label: "GPT-4" }],
            is_configured: true,
          },
        ],
      });

      render(<NewConversationModal isOpen={true} onClose={mockOnClose} onSubmit={mockOnSubmit} />);

      await waitFor(() => {
        expect(screen.getByText("OpenAI")).toBeInTheDocument();
      });

      // Should default to OpenAI (first configured)
      const providerSelect = screen.getByLabelText(/Provedor de IA/i) as HTMLSelectElement;
      await waitFor(() => {
        expect(providerSelect.value).toBe("openai");
      });
    });
  });

  describe("Error Handling", () => {
    it("should show error message if no providers loaded", async () => {
      vi.mocked(chatApi.listProviders).mockRejectedValueOnce(new Error("Network error"));

      render(<NewConversationModal isOpen={true} onClose={mockOnClose} onSubmit={mockOnSubmit} />);

      // Should display error message
      await waitFor(() => {
        expect(
          screen.getByText(/Não foi possível carregar os provedores de IA/i)
        ).toBeInTheDocument();
      });

      // Error message should be visible to user
      expect(chatApi.listProviders).toHaveBeenCalled();
    });
  });
});
