"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useEffect } from "react";
import type { components } from "@/types/api";

type ConversationRead = components["schemas"]["ConversationRead"];

// Validation schema
const editConversationSchema = z.object({
  title: z.string().min(1, "Título é obrigatório").max(255, "Título muito longo"),
  system_prompt: z.string().optional(),
});

type EditConversationFormData = z.infer<typeof editConversationSchema>;

interface EditConversationModalProps {
  isOpen: boolean;
  conversation: ConversationRead | null;
  onClose: () => void;
  onSubmit: (data: EditConversationFormData) => Promise<void>;
  isSubmitting?: boolean;
}

export function EditConversationModal({
  isOpen,
  conversation,
  onClose,
  onSubmit,
  isSubmitting = false,
}: EditConversationModalProps) {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<EditConversationFormData>({
    resolver: zodResolver(editConversationSchema),
    defaultValues: {
      title: conversation?.title || "",
      system_prompt: conversation?.system_prompt || "",
    },
  });

  // Reset form when conversation changes or modal opens
  useEffect(() => {
    if (conversation && isOpen) {
      reset({
        title: conversation.title,
        system_prompt: conversation.system_prompt || "",
      });
    }
  }, [conversation, isOpen, reset]);

  const handleFormSubmit = async (data: EditConversationFormData) => {
    await onSubmit(data);
    onClose();
  };

  if (!isOpen || !conversation) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
      <div className="bg-white rounded-lg shadow-xl max-w-lg w-full mx-4 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900">Editar Conversa</h2>
          <button
            onClick={onClose}
            disabled={isSubmitting}
            className="text-gray-400 hover:text-gray-600 transition-colors disabled:opacity-50"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit(handleFormSubmit)} className="p-6 space-y-4">
          {/* Provider and Model info (read-only) */}
          <div className="bg-gray-50 p-4 rounded-lg">
            <p className="text-sm text-gray-600 mb-2">
              <span className="font-medium">Provedor:</span>{" "}
              <span className="font-mono">{conversation.ai_provider}</span>
            </p>
            <p className="text-sm text-gray-600">
              <span className="font-medium">Modelo:</span>{" "}
              <span className="font-mono">{conversation.ai_model}</span>
            </p>
            <p className="text-xs text-gray-500 mt-2">
              O provedor e modelo não podem ser alterados após criação
            </p>
          </div>

          {/* Title */}
          <div>
            <label htmlFor="edit-title" className="block text-sm font-medium text-gray-700 mb-1">
              Título <span className="text-red-500">*</span>
            </label>
            <input
              {...register("title")}
              id="edit-title"
              type="text"
              placeholder="Ex: Ajuda com Python"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            {errors.title && <p className="mt-1 text-sm text-red-600">{errors.title.message}</p>}
          </div>

          {/* System Prompt */}
          <div>
            <label
              htmlFor="edit-system-prompt"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Prompt do Sistema (opcional)
            </label>
            <textarea
              {...register("system_prompt")}
              id="edit-system-prompt"
              rows={4}
              placeholder="Ex: Você é um assistente especializado em programação Python..."
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
            />
            <p className="mt-1 text-xs text-gray-500">
              Define o comportamento e personalidade da IA
            </p>
            {errors.system_prompt && (
              <p className="mt-1 text-sm text-red-600">{errors.system_prompt.message}</p>
            )}
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg font-medium hover:bg-gray-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
            >
              {isSubmitting ? (
                <>
                  <svg
                    className="animate-spin -ml-1 mr-2 h-4 w-4"
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
                  Salvando...
                </>
              ) : (
                "Salvar Alterações"
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
