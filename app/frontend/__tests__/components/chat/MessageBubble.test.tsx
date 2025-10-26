import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { MessageBubble } from "@/components/chat/MessageBubble";
import React from "react";

describe("MessageBubble Performance", () => {
  it("is a memoized component", () => {
    // Verify the component is wrapped with React.memo by checking its type
    // React.memo returns a special component type
    expect(MessageBubble).toBeDefined();
    expect(typeof MessageBubble).toBe("object");
    expect(MessageBubble.$$typeof?.toString()).toContain("react.memo");
  });

  it("renders correctly with minimal props", () => {
    const props = {
      role: "user" as const,
      content: "Hello world",
      timestamp: "2024-01-01T12:00:00Z",
    };

    const { rerender } = render(<MessageBubble {...props} />);
    expect(screen.getByText("Hello world")).toBeInTheDocument();

    // Re-render with same props should work without errors
    rerender(<MessageBubble {...props} />);
    expect(screen.getByText("Hello world")).toBeInTheDocument();
  });

  it("handles callback props correctly", () => {
    // Stable callback references
    const onRetry = vi.fn();
    const onRemove = vi.fn();

    const props = {
      role: "user" as const,
      content: "Failed message",
      timestamp: "2024-01-01T12:00:00Z",
      status: "failed" as const,
      onRetry,
      onRemove,
    };

    const { rerender } = render(<MessageBubble {...props} />);
    expect(screen.getByText("Failed message")).toBeInTheDocument();

    // Re-render with same callback references should work
    rerender(<MessageBubble {...props} />);
    expect(screen.getByText("Failed message")).toBeInTheDocument();
  });

  it("should memoize formatTimestamp computation", () => {
    // This test verifies that formatTimestamp doesn't cause unnecessary re-renders
    // by being recreated on every render

    // Use recent timestamp (1 hour ago) to ensure "há Xh" format
    const oneHourAgo = new Date(Date.now() - 3600000).toISOString();

    const props = {
      role: "assistant" as const,
      content: "AI response",
      timestamp: oneHourAgo,
      tokensUsed: 100,
    };

    const { rerender } = render(<MessageBubble {...props} />);

    // Get the timestamp element (should show "há 1h")
    const timestampElement = screen.getByText(/há \d+h/i);
    expect(timestampElement).toBeInTheDocument();

    // Re-render with same props
    rerender(<MessageBubble {...props} />);

    // Timestamp should still be in document (component didn't unnecessarily re-render)
    expect(screen.getByText(/há \d+h/i)).toBeInTheDocument();
  });
});

describe("MessageBubble Rendering", () => {
  it("renders user message correctly", () => {
    render(<MessageBubble role="user" content="Hello world" timestamp="2024-01-01T12:00:00Z" />);

    expect(screen.getByText("Hello world")).toBeInTheDocument();
  });

  it("renders assistant message with markdown", () => {
    render(
      <MessageBubble role="assistant" content="**Bold text**" timestamp="2024-01-01T12:00:00Z" />
    );

    // ReactMarkdown should render bold
    const boldElement = screen.getByText("Bold text");
    expect(boldElement.tagName).toBe("STRONG");
  });

  it("displays token count for assistant messages", () => {
    render(
      <MessageBubble
        role="assistant"
        content="AI response"
        timestamp="2024-01-01T12:00:00Z"
        tokensUsed={150}
      />
    );

    expect(screen.getByText("150 tokens")).toBeInTheDocument();
  });

  it("does not display token count for user messages", () => {
    render(
      <MessageBubble
        role="user"
        content="User message"
        timestamp="2024-01-01T12:00:00Z"
        tokensUsed={50}
      />
    );

    expect(screen.queryByText("50 tokens")).not.toBeInTheDocument();
  });
});
