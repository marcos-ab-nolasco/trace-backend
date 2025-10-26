"use client";

import { useState } from "react";
import { ConversationList } from "./ConversationList";
import { NewConversationModal } from "./NewConversationModal";
import type { components } from "@/types/api";

type ConversationRead = components["schemas"]["ConversationRead"];
type ConversationCreate = components["schemas"]["ConversationCreate"];

interface SidebarProps {
  conversations: ConversationRead[];
  currentConversationId: string | null;
  isLoading: boolean;
  error: string | null;
  onSelectConversation: (id: string) => void;
  onDeleteConversation: (id: string) => void;
  onCreateConversation: (data: ConversationCreate) => Promise<void>;
  onRetry?: () => void;
}

export function Sidebar({
  conversations,
  currentConversationId,
  isLoading,
  error,
  onSelectConversation,
  onDeleteConversation,
  onCreateConversation,
  onRetry,
}: SidebarProps) {
  const [isMobileOpen, setIsMobileOpen] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isCreating, setIsCreating] = useState(false);

  const handleNewConversation = () => {
    setIsModalOpen(true);
  };

  const handleCreateConversation = async (data: ConversationCreate) => {
    setIsCreating(true);
    try {
      await onCreateConversation(data);
      setIsModalOpen(false);
      setIsMobileOpen(false); // Close mobile sidebar after creating
    } catch (error) {
      // Error is handled by the store
      console.error("Failed to create conversation:", error);
    } finally {
      setIsCreating(false);
    }
  };

  const handleSelectConversation = (id: string) => {
    onSelectConversation(id);
    setIsMobileOpen(false); // Close mobile sidebar after selecting
  };

  return (
    <>
      {/* Mobile toggle button */}
      <button
        onClick={() => setIsMobileOpen(!isMobileOpen)}
        className="lg:hidden fixed top-4 left-4 z-50 p-2 bg-blue-600 text-white rounded-lg shadow-lg hover:bg-blue-700 transition-colors"
        aria-label="Toggle sidebar"
      >
        {isMobileOpen ? (
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        ) : (
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 6h16M4 12h16M4 18h16"
            />
          </svg>
        )}
      </button>

      {/* Mobile overlay */}
      {isMobileOpen && (
        <div
          className="lg:hidden fixed inset-0 bg-black bg-opacity-50 z-30"
          onClick={() => setIsMobileOpen(false)}
        />
      )}

      {/* Sidebar container */}
      <div
        className={`
          fixed lg:static inset-y-0 left-0 z-40
          w-80 lg:w-80
          transform transition-transform duration-300 ease-in-out
          ${isMobileOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"}
          border-r border-gray-200
          bg-white
        `}
      >
        <ConversationList
          conversations={conversations}
          currentConversationId={currentConversationId}
          isLoading={isLoading}
          error={error}
          onSelectConversation={handleSelectConversation}
          onDeleteConversation={onDeleteConversation}
          onNewConversation={handleNewConversation}
          onRetry={onRetry}
        />
      </div>

      {/* New Conversation Modal */}
      <NewConversationModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSubmit={handleCreateConversation}
        isSubmitting={isCreating}
      />
    </>
  );
}
