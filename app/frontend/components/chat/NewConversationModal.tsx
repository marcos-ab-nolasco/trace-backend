"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useEffect, useMemo, useState } from "react";
import * as chatApi from "@/lib/api/chat";

type ProviderOption = {
  id: string;
  label: string;
  models: { value: string; label: string }[];
  is_configured: boolean;
};

const conversationSchema = z.object({
  title: z.string().min(1, "Título é obrigatório").max(255, "Título muito longo"),
  ai_provider: z.string().min(1, "Provedor é obrigatório"),
  ai_model: z.string().min(1, "Modelo é obrigatório"),
  system_prompt: z.string().optional(),
});

type ConversationFormData = z.infer<typeof conversationSchema>;

interface NewConversationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: ConversationFormData) => Promise<void>;
  isSubmitting?: boolean;
}

export function NewConversationModal({
  isOpen,
  onClose,
  onSubmit,
  isSubmitting = false,
}: NewConversationModalProps) {
  const {
    register,
    handleSubmit,
    watch,
    setValue,
    reset,
    getValues,
    formState: { errors },
  } = useForm<ConversationFormData>({
    resolver: zodResolver(conversationSchema),
    defaultValues: {
      title: "",
      ai_provider: "",
      ai_model: "",
      system_prompt: "",
    },
  });

  const [providers, setProviders] = useState<ProviderOption[]>([]);
  const [isLoadingProviders, setIsLoadingProviders] = useState<boolean>(true);
  const [providerError, setProviderError] = useState<string | null>(null);

  const selectedProvider = watch("ai_provider");

  const selectedProviderInfo = useMemo(
    () => providers.find((provider) => provider.id === selectedProvider),
    [providers, selectedProvider]
  );

  useEffect(() => {
    let isMounted = true;

    const loadProviders = async () => {
      setIsLoadingProviders(true);
      setProviderError(null);

      try {
        const data = await chatApi.listProviders();

        if (!isMounted) return;
        setProviders(data.providers ?? []);
      } catch (error) {
        if (!isMounted) return;
        console.error("Failed to load AI providers", error);
        setProviderError(
          "Não foi possível carregar os provedores de IA. Verifique o backend e tente novamente."
        );
        setProviders([]);
      } finally {
        if (isMounted) {
          setIsLoadingProviders(false);
        }
      }
    };

    loadProviders();

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedProvider) {
      setValue("ai_model", "");
      return;
    }

    const provider = providers.find((item) => item.id === selectedProvider);
    if (!provider) {
      setValue("ai_model", "");
      return;
    }

    const currentModel = getValues("ai_model");
    const hasModel = provider.models.some((model) => model.value === currentModel);
    if (!hasModel) {
      const firstModel = provider.models[0]?.value ?? "";
      setValue("ai_model", firstModel);
    }
  }, [selectedProvider, providers, setValue, getValues]);

  useEffect(() => {
    if (providers.length === 0) {
      return;
    }

    const currentProvider = getValues("ai_provider");
    const availableIds = providers.map((provider) => provider.id);
    const firstConfigured = providers.find((provider) => provider.is_configured);
    const fallback = firstConfigured ?? providers[0];

    if (!currentProvider || !availableIds.includes(currentProvider)) {
      setValue("ai_provider", fallback.id);
      const firstModel = fallback.models[0]?.value ?? "";
      setValue("ai_model", firstModel);
    }
  }, [providers, getValues, setValue]);

  useEffect(() => {
    if (!isOpen) {
      const defaultProvider = providers.find((provider) => provider.is_configured) ?? providers[0];
      reset({
        title: "",
        ai_provider: defaultProvider?.id ?? "",
        ai_model: defaultProvider?.models[0]?.value ?? "",
        system_prompt: "",
      });
    }
  }, [isOpen, reset, providers]);

  const handleFormSubmit = async (data: ConversationFormData) => {
    if (!providers.length) {
      setProviderError("Nenhum provedor de IA foi carregado.");
      return;
    }

    await onSubmit(data);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
      <div className="bg-white rounded-lg shadow-xl max-w-lg w-full mx-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900">Nova Conversa</h2>
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

        <form onSubmit={handleSubmit(handleFormSubmit)} className="p-6 space-y-4">
          <div>
            <label htmlFor="title" className="block text-sm font-medium text-gray-700 mb-1">
              Título <span className="text-red-500">*</span>
            </label>
            <input
              {...register("title")}
              id="title"
              type="text"
              placeholder="Ex: Ajuda com Python"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            {errors.title && <p className="mt-1 text-sm text-red-600">{errors.title.message}</p>}
          </div>

          <div>
            <label htmlFor="ai_provider" className="block text-sm font-medium text-gray-700 mb-1">
              Provedor de IA <span className="text-red-500">*</span>
            </label>
            <select
              {...register("ai_provider")}
              id="ai_provider"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={isLoadingProviders}
            >
              {isLoadingProviders && <option>Carregando provedores...</option>}
              {providers.map((provider) => (
                <option key={provider.id} value={provider.id}>
                  {provider.label}
                  {!provider.is_configured ? " (não configurado)" : ""}
                </option>
              ))}
            </select>
            {errors.ai_provider && (
              <p className="mt-1 text-sm text-red-600">{errors.ai_provider.message}</p>
            )}
            {providerError && <p className="mt-1 text-sm text-red-600">{providerError}</p>}
          </div>

          <div>
            <label htmlFor="ai_model" className="block text-sm font-medium text-gray-700 mb-1">
              Modelo <span className="text-red-500">*</span>
            </label>
            <select
              {...register("ai_model")}
              id="ai_model"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={isLoadingProviders || (selectedProviderInfo?.models.length ?? 0) === 0}
            >
              {(selectedProviderInfo?.models ?? []).map((model) => (
                <option key={model.value} value={model.value}>
                  {model.label}
                </option>
              ))}
            </select>
            {errors.ai_model && (
              <p className="mt-1 text-sm text-red-600">{errors.ai_model.message}</p>
            )}
            <p className="mt-1 text-xs text-gray-500">
              Os modelos exibidos dependem do provedor selecionado e da configuração do backend.
            </p>
          </div>

          <div>
            <label htmlFor="system_prompt" className="block text-sm font-medium text-gray-700 mb-1">
              Prompt do Sistema (opcional)
            </label>
            <textarea
              {...register("system_prompt")}
              id="system_prompt"
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

          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition disabled:opacity-50"
              disabled={isSubmitting}
            >
              Cancelar
            </button>
            <button
              type="submit"
              className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition disabled:opacity-50"
              disabled={isSubmitting || isLoadingProviders}
            >
              {isSubmitting ? "Criando..." : "Criar Conversa"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
