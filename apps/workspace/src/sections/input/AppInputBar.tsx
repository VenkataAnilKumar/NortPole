"use client";

import { ActionButton, NativeInput } from "@opal/components";
import { useNavigation } from "@opal/navigation";
import { Section } from "@opal/layouts";
import { IconLoader } from "@opal/loaders";
import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useTranslations } from "next-intl";
import { MinimalAgent } from "@/lib/agents/types";
import { useQuickAddItems } from "./useQuickAddItems";
import ExpenseReviewForm from "@/sections/input/ExpenseReviewForm";
import DocumentReviewForm from "@/sections/input/DocumentReviewForm";
import type { ComposerSelection } from "@/app/app/types";
import { InputPrompt } from "@/app/app/types";
import { LlmManager } from "@/lib/hooks";
import usePromptShortcuts from "@/hooks/usePromptShortcuts";
import { useContentEditable } from "@/hooks/useContentEditable";
import useFilter from "@/hooks/useFilter";
import { useAvailableSources } from "@/lib/connectors/hooks";
import { MinimalNortPoleDocument } from "@/lib/search/types";
import { ChatState, MAX_QUEUED_MESSAGES } from "@/app/app/types";
import { useQueuedMessageNavigation } from "@/hooks/useQueuedMessageNavigation";
import type { ToolConfigurationHandle } from "@/lib/tools/hooks";
import { effectiveChatPreferredToolId } from "@/lib/plugins/chat";
import type { MemberPlugin } from "@/lib/plugins/member";
import { useAppPosition } from "@/lib/navigation/hooks";
import { settleChatSession } from "@/lib/chat/settleChatSession";
import { useDraft, draftKey } from "@/hooks/useDraft";
import { getPastedFilesIfNoText } from "@/lib/clipboard";
import PasteTilePopover from "@/sections/input/PasteTilePopover";
import { cn } from "@opal/utils";
import { firstStrongTextDir } from "@/lib/rehypeDirection";
import { Disabled } from "@opal/core";
import { useUser } from "@/providers/UserProvider";
import { useSettings } from "@/lib/settings/hooks";
import { useProjectsContext } from "@/lib/projects/providers";
import { useActiveProject, useProjects } from "@/lib/projects/hooks";
import { FileCard } from "@/sections/cards/FileCard";
import { ProjectFile } from "@/lib/projects/types";
import { isFilePending } from "@/lib/projects/utils";
import FilePickerPopover from "@/refresh-components/popovers/FilePickerPopover";
import { ToolsPopover } from "@/lib/tools/components";
import ModelSelector from "@/sections/model-selector/ModelSelector";
import MultiModelSelector from "@/sections/model-selector/MultiModelSelector";
import type { UseMultiModelChatReturn } from "@/hooks/useMultiModelChat";
import type { LLMOption } from "@/lib/languageModels/types";
import RoutePicker from "@/sections/model-selector/RoutePicker";
import { useRoutePolicy } from "@/lib/routePolicy/hooks";
import MCPConnectionPrompt from "@/lib/mcp/components/MCPConnectionPrompt";
import {
  getIconForAction,
  hasSearchToolsAvailable,
} from "@/app/app/services/actionUtils";
import {
  SvgArrowUp,
  SvgAudio,
  SvgSettings,
  SvgGlobe,
  SvgHourglass,
  SvgMicrophone,
  SvgPaperclip,
  SvgPlus,
  SvgSearch,
  SvgStop,
  SvgX,
  SvgRefreshCw,
} from "@opal/icons";
import {
  Button,
  LineItemButton,
  Popover,
  SelectButton,
  Spacer,
  Text,
} from "@opal/components";
import { useQueryController } from "@/providers/QueryControllerProvider";
import { takeSearchEvidence } from "@/lib/chat/searchHandoff";
import type { AgentPilotInput } from "@/lib/agents/pilots";
import { PilotDocumentPicker } from "./PilotDocumentPicker";
import { ReportingInputs, type ReportingSelection } from "./ReportingInputs";
import { useIncognito } from "@/providers/IncognitoProvider";
import MicrophoneButton from "@/sections/input/MicrophoneButton";
import Waveform from "@/components/voice/Waveform";
import { useVoiceMode } from "@/providers/VoiceModeProvider";
import { useVoiceStatus } from "@/hooks/useVoiceStatus";
import {
  useCurrentQueuedMessages,
  useCurrentLatestMessageRenderComplete,
  useChatSessionStore,
} from "@/app/app/stores/useChatSessionStore";
import QueuedMessageBar from "@/sections/input/QueuedMessageBar";
import { handleInputNavKeys } from "@/sections/input/inputBarKeys";

export interface AppInputBarHandle {
  reset: () => void;
  /** Puts back a message and files that failed to send, unless a newer draft exists. */
  restore: (message: string, files: ProjectFile[], selections?: ComposerSelection[]) => void;
  focus: () => void;
  insertStarter: (prompt: string) => void;
  prepareScopeChange: (enteringNewSession: boolean) => void;
}

export interface AppInputBarProps {
  initialMessage?: string;
  stopGenerating: () => void;
  onSubmit: (message: string, selections?: ComposerSelection[]) => void;
  showQuickAdd?: boolean;
  previewOnly?: boolean;
  agentPilot?: AgentPilotInput | null;
  contextPickers?: React.ReactNode;
  llmManager: LlmManager;
  chatState: ChatState;

  // agents
  activeAgent: MinimalAgent | undefined;
  memberPlugins?: readonly MemberPlugin[];

  handleFileUpload: (files: File[]) => void;
  deepResearchEnabled: boolean;
  setPresentingDocument?: (document: MinimalNortPoleDocument) => void;
  toggleDeepResearch: () => void;
  isMultiModelActive?: boolean;
  modelComparison?: Pick<UseMultiModelChatReturn, "selectedModels" | "addModel" | "removeModel" | "replaceModel">;
  disabled: boolean;
  /**
   * Owned by the surface rather than read here, because the send path reads
   * the same one and two instances would drift.
   */
  toolConfiguration: ToolConfigurationHandle;
  ref?: React.Ref<AppInputBarHandle>;
  // Side panel tab reading
  tabReadingEnabled?: boolean;
  currentTabUrl?: string | null;
  onToggleTabReading?: () => void;
}

const AppInputBar = React.memo(
  ({
    initialMessage = "",
    stopGenerating,
    onSubmit,
    contextPickers,
    showQuickAdd = false,
    previewOnly = false,
    agentPilot,
    chatState,
    activeAgent,
    memberPlugins,
    handleFileUpload,
    llmManager,
    deepResearchEnabled,
    toggleDeepResearch,
    isMultiModelActive,
    modelComparison,
    setPresentingDocument,
    disabled,
    toolConfiguration,
    ref,
    tabReadingEnabled,
    currentTabUrl,
    onToggleTabReading,
  }: AppInputBarProps) => {
    const t = useTranslations("chat.input");
    const quickAddCopy = useTranslations("chat.quickAdd");
    const expenseCopy = useTranslations("chat.expenseReview");
    const reportingCopy = useTranslations("agents.reporting");
    const spreadsheetCopy = useTranslations("agents.spreadsheetAnalysis");
    const meetingCopy = useTranslations("agents.meetingRecap");
    const meetingPilot = agentPilot?.kind === "meeting-recap";
    const modelRouteCopy = useTranslations("chat.modelRoute");
    const { incognitoEnabled } = useIncognito();
    const [isRecording, setIsRecording] = useState(false);
    const [recordingCycleCount, setRecordingCycleCount] = useState(0);
    const [isMuted, setIsMuted] = useState(false);
    const [audioLevel, setAudioLevel] = useState(0);
    const stopRecordingRef = useRef<(() => Promise<string | null>) | null>(
      null
    );
    const setMutedRef = useRef<((muted: boolean) => void) | null>(null);
    const queuedMessages = useCurrentQueuedMessages();
    const currentSessionId = useChatSessionStore(
      (state) => state.currentSessionId
    );
    const [checkingSessions, setCheckingSessions] = useState<Set<string>>(
      () => new Set()
    );
    const isCheckingCompletion =
      currentSessionId !== null && checkingSessions.has(currentSessionId);
    const canStopGeneration =
      chatState === "loading" || chatState === "streaming";
    const tReadiness = useTranslations("chat.readiness");
    const queuedMessagesPaused = useChatSessionStore(
      (state) =>
        state.sessions.get(state.currentSessionId ?? "")
          ?.queuedMessagesPaused ?? false
    );
    const latestMessageRenderComplete = useCurrentLatestMessageRenderComplete();
    const enqueueCurrentMessage = useChatSessionStore(
      (state) => state.enqueueCurrentMessage
    );
    const removeCurrentQueuedMessage = useChatSessionStore(
      (state) => state.removeCurrentQueuedMessage
    );
    const { user, isAdmin } = useUser();
    const isAutoSending = useRef(false);
    const inputWrapperRef = useRef<HTMLDivElement>(null);
    const {
      ref: inputRef,
      message,
      setMessage,
      clearMessage,
      handleInput,
      handleCompositionStart,
      handleCompositionEnd,
      pasteText,
      handleCopy,
      handleCut,
      setCursorToEnd,
      handleTileMouseDown,
      handleTileClick,
      handleTileKeyDown,
      tilePopover,
      dismissTilePopover,
      updateTileText,
      expandTile,
    } = useContentEditable({
      initialContent: initialMessage,
      wrapperRef: inputWrapperRef,
      pasteTilesEnabled: user?.preferences?.paste_as_tile ?? false,
    });

    // Keyboard navigation + highlight state for the queued-message bar
    // (shared with the Craft input bar).
    const queueNav = useQueuedMessageNavigation({
      messages: queuedMessages,
      inputIsEmpty: !message,
      onRemove: removeCurrentQueuedMessage,
      onEdit: (text, queued) => {
        setMessage(text);
        if (queued?.selections?.length) {
          setContext({ scope: selectionScope, items: queued.selections });
        }
      },
    });

    const filesWrapperRef = useRef<HTMLDivElement>(null);
    const filesContentRef = useRef<HTMLDivElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const { state, setAppMode } = useQueryController();
    const isClassifying = state.phase === "classifying";
    const isSearchActive =
      state.phase === "searching" || state.phase === "search-results";
    const {
      stopTTS,
      isTTSPlaying,
      isManualTTSPlaying,
      isTTSLoading,
      isAwaitingAutoPlaybackStart,
      isTTSMuted,
      toggleTTSMute,
      voiceModeEnabled,
      setVoiceModeEnabled,
    } = useVoiceMode();
    const { sttEnabled, ttsEnabled } = useVoiceStatus();
    // Show mic button: always if STT configured, or greyed-out for admins to prompt setup
    const showMicButton = sttEnabled || isAdmin;
    const requiredModelId = activeAgent?.id
      ? activeAgent.default_model_configuration_id
      : null;
    const modelLabel =
      llmManager.llmProviders
        ?.flatMap((provider) => provider.model_configurations)
        .find(
          (model) =>
            model.id === (requiredModelId ?? llmManager.currentLlm?.modelConfigurationId)
        )
        ?.effectiveDisplayName ??
      (requiredModelId ? undefined : llmManager.currentLlm?.modelName);
    const isVoicePlaybackActive =
      isTTSPlaying || isTTSLoading || isAwaitingAutoPlaybackStart;
    const isVoicePlaybackControllable = isVoicePlaybackActive && !isRecording;
    const isTTSActuallySpeaking = isTTSPlaying || isManualTTSPlaying;
    const appPosition = useAppPosition();
    const navigation = useNavigation();
    const isNewSession = appPosition.isNewSession();
    const appMode = state.phase === "idle" ? state.appMode : undefined;
    const isSearchMode =
      (isNewSession && appMode === "search") || isSearchActive;
    const { data: routePolicy } = useRoutePolicy();
    const modelBlockedReason = (option: LLMOption) => {
      if (option.isAuto) return undefined;
      const blocked = routePolicy?.routes.find((route) =>
        route.provider_id === option.providerId && !route.allowed
      );
      return blocked ? blocked.reason ?? modelRouteCopy("blocked") : undefined;
    };
    const showRoutePicker =
      llmManager.chatModelMode !== undefined && !isMultiModelActive &&
      !isSearchMode && Boolean(routePolicy?.routes.length);
    const combinedSettingsData = useSettings();

    const activePlaceholder =
      queuedMessages.length > 0 && !message
        ? t("appInputBar.input.queuedPlaceholder")
        : isRecording
          ? t("appInputBar.input.listeningPlaceholder")
          : isVoicePlaybackActive
            ? t("appInputBar.input.speakingPlaceholder", {
                appName: combinedSettingsData.appName,
              })
            : isSearchMode
              ? t("appInputBar.input.searchPlaceholder")
              : meetingPilot ? meetingCopy("placeholder") : t("appInputBar.input.placeholder");

    // Keyed by chat session id, or "new" until the session is created.
    const chatSessionId = appPosition.chat();
    const chatDraftStorageKey = draftKey("chat", chatSessionId ?? "new");
    const {
      draft: chatDraft,
      loaded: chatDraftLoaded,
      save: saveChatDraft,
      clear: clearChatDraft,
    } = useDraft<string>({ key: chatDraftStorageKey });
    const draftSeededRef = useRef(false);
    const skipNextDraftSaveRef = useRef(false);
    const keepDraftOnNewSessionRef = useRef(false);
    const prevDraftKeyRef = useRef(chatDraftStorageKey);
    // Snapshot of message, read non-reactively in the restore effect so seeding
    // doesn't re-run on every keystroke.
    const messageRef = useRef(message);
    const isRecordingRef = useRef(isRecording);

    useEffect(() => {
      messageRef.current = message;
    }, [message]);

    useEffect(() => {
      draftSeededRef.current = false;
      // Clear the previous session's leftover text instead of leaking it into
      // this one.
      if (prevDraftKeyRef.current !== chatDraftStorageKey) {
        prevDraftKeyRef.current = chatDraftStorageKey;
        clearMessage();
      }
    }, [chatDraftStorageKey, clearMessage]);

    // Restore once read: a URL prompt wins and a non-empty input is never
    // clobbered.
    useEffect(() => {
      if (!chatDraftLoaded || draftSeededRef.current) return;
      draftSeededRef.current = true;
      if (chatDraft && !initialMessage && !messageRef.current) {
        // Skip the save effect's next run; it would fire with the stale empty
        // message and wipe what we just seeded.
        skipNextDraftSaveRef.current = true;
        setMessage(chatDraft);
      }
    }, [chatDraftLoaded, chatDraft, initialMessage, setMessage]);

    useEffect(() => {
      if (!chatDraftLoaded || !draftSeededRef.current) return;
      if (skipNextDraftSaveRef.current) {
        skipNextDraftSaveRef.current = false;
        return;
      }
      saveChatDraft(message);
    }, [message, chatDraftLoaded, saveChatDraft]);

    const handleRecordingChange = useCallback((nextIsRecording: boolean) => {
      const wasRecording = isRecordingRef.current;
      isRecordingRef.current = nextIsRecording;
      if (!wasRecording && nextIsRecording) {
        setRecordingCycleCount((count) => count + 1);
      }
      setIsRecording(nextIsRecording);
    }, []);

    const selectionScope = JSON.stringify([
      chatSessionId,
      appPosition.project(),
      activeAgent?.id,
    ]);
    const [context, setContext] = useState<{
      scope: typeof selectionScope;
      items: ComposerSelection[];
    } | null>(null);
    useEffect(() => {
      if (!isNewSession || !user?.id || activeAgent?.id === undefined) return;
      const evidence = takeSearchEvidence(String(user.id));
      if (!evidence.length) return;
      setAppMode("chat");
      setContext({ scope: selectionScope, items: evidence });
      inputRef.current?.focus();
    }, [activeAgent?.id, inputRef, isNewSession, selectionScope, setAppMode, user?.id]);

    const [review, setReview] = useState<{
      scope: string;
      kind: "expense-review" | "document-review";
      library?: string;
      option?: string;
    } | null>(null);
    const activeReview = review?.scope === selectionScope && !isSearchMode ? review : null;
    const selections = context?.scope === selectionScope ? context.items : undefined;
    const pilotDocuments = selections?.filter((item) => item.kind === "search-result") ?? [];
    const missingPilotDocuments = agentPilot?.kind === "document-analysis" && pilotDocuments.length === 0;
    const { currentMessageFiles, setCurrentMessageFiles } = useProjectsContext();
    const reporting = agentPilot?.kind === "reporting" ? agentPilot : null;
    const spreadsheetPilot = agentPilot?.kind === "spreadsheet-analysis";
    const [spreadsheetError, setSpreadsheetError] = useState<string | null>(null);
    const missingSpreadsheet = spreadsheetPilot && (
      currentMessageFiles.length !== 1 || !/\.(csv|xlsx)$/i.test(currentMessageFiles[0]?.name ?? "")
    );
    const [reportSelection, setReportSelection] = useState<{
      scope: string;
      value: ReportingSelection;
    } | null>(null);
    const report = reportSelection?.scope === selectionScope ? reportSelection.value : undefined;
    const reportStart = report?.start ?? "";
    const reportEnd = report?.end ?? "";
    const selectedReportSources = JSON.stringify(reporting?.libraries
      .filter((library) => report?.libraryIds.includes(library.id)).map((library) => library.name) ?? []);
    const missingReportInputs = Boolean(reporting && (
      !reportStart || !reportEnd || reportStart > reportEnd || selectedReportSources === "[]"
    ));
    const missingPilotInputs = missingPilotDocuments || missingReportInputs || missingSpreadsheet;
    const formatMessage = useCallback((text: string) => reporting
      ? `Reporting period: ${reportStart} to ${reportEnd}\nKnowledge sources: ${selectedReportSources}\n\n${text.trim()}`
      : text, [reporting, reportStart, reportEnd, selectedReportSources]);
    const matches = (first: ComposerSelection, second: ComposerSelection) =>
      first.kind === second.kind && first.id === second.id;
    const hasSelection = (item: ComposerSelection) =>
      selections?.some((selected) => matches(selected, item)) ?? false;
    const toggleSelection = (item: ComposerSelection) => {
      setContext((previous) => {
        const items = previous?.scope === selectionScope ? previous.items : [];
        return {
          scope: selectionScope,
          items: items.some((selected) => matches(selected, item))
            ? items.filter((selected) => !matches(selected, item))
            : [...items, item],
        };
      });
    };
    const insertStarter = (prompt: string) => {
      if (disabled) return;
      const existing = message.trimEnd();
      setMessage(existing ? `${existing}\n\n${prompt}` : prompt);
      inputRef.current?.focus();
      setCursorToEnd();
    };
    const { items: quickAddItems, libraries, reviewPacks } = useQuickAddItems({
      enabled: showQuickAdd && !previewOnly,
      agent: activeAgent,
      select: toggleSelection,
      insertPrompt: insertStarter,
      openExpenseReview: () => setReview({ scope: selectionScope, kind: "expense-review" }),
      openDocumentReview: () => setReview({ scope: selectionScope, kind: "document-review" }),
    });
    const enqueueWithSelections = () => {
      enqueueCurrentMessage(formatMessage(message.trim()), selections);
      setContext(null);
    };

    // Wrapper for onSubmit that stops TTS first to prevent overlapping voices
    const handleSubmit = useCallback(
      (text: string) => {
        stopTTS();
        setReview(null);
        if (selections?.length) {
          onSubmit(text, selections);
          setContext(null);
        } else {
          onSubmit(text);
        }
      },
      [stopTTS, onSubmit, selections]
    );
    const submitMessage = useCallback(
      (text: string) => {
        if (chatState !== "input" || !text.trim() || missingPilotInputs) {
          return;
        }
        handleSubmit(formatMessage(text));
        clearChatDraft();
      },
      [chatState, handleSubmit, clearChatDraft, missingPilotInputs, formatMessage]
    );

    // Expose reset and focus methods to parent via ref
    React.useImperativeHandle(ref, () => ({
      reset: () => {
        if (!isAutoSending.current) {
          clearMessage();
          clearChatDraft();
        }
      },
      restore: (text, files, restoredSelections) => {
        // Keep a draft the user started while the failed send was pending.
        if (message.trim() || currentMessageFiles.length > 0) return;
        setMessage(text);
        setCurrentMessageFiles(files);
        const restoredReview = restoredSelections?.find(
          ({ kind }) => kind === "expense-review" || kind === "document-review"
        );
        if (restoredReview) {
          setReview({
            scope: selectionScope,
            kind: restoredReview.kind === "expense-review" ? "expense-review" : "document-review",
            option: restoredReview.id,
            library: restoredSelections?.find(({ kind }) => kind === "knowledge")?.id,
          });
          return;
        }
        if (!selections?.length && restoredSelections?.length) {
          setContext({ scope: selectionScope, items: restoredSelections });
        }
        setCursorToEnd();
      },
      insertStarter,
      prepareScopeChange: (enteringNewSession) => {
        keepDraftOnNewSessionRef.current = enteringNewSession;
        setContext(null);
        setReview(null);
      },
      focus: () => {
        inputRef.current?.focus();
        setCursorToEnd();
      },
    }));

    const submitReview = (kind: "expense-review" | "document-review", library: string, option: string) => {
      const isExpense = kind === "expense-review";
      const request = isExpense ? expenseCopy("request") : "Review the attached document against the selected Knowledge library.";
      const notes = message.trim();
      const text = notes === request || notes.startsWith(`${request}\n\n`)
        ? notes
        : [request, notes].filter(Boolean).join("\n\n");
      stopTTS();
      setReview(null);
      setContext(null);
      onSubmit(text, [
        { kind: "knowledge", id: library, label: library },
        { kind, id: option, label: isExpense ? expenseCopy("title") : "Document Review" },
      ]);
    };

    // Sync non-empty prop changes to internal state (e.g. NRFPage reads URL params
    // after mount). Intentionally skips empty strings — clearing is handled via the
    // imperative ref.reset() method, not by passing initialMessage="".
    useEffect(() => {
      if (initialMessage) {
        setMessage(initialMessage);
      }
    }, [initialMessage]);
    const shouldShowRecordingWaveformBelow =
      isRecording &&
      !isVoicePlaybackActive &&
      (isNewSession || recordingCycleCount === 1);

    useEffect(() => {
      const keepDraft = keepDraftOnNewSessionRef.current;
      keepDraftOnNewSessionRef.current = false;
      if (isNewSession && !initialMessage && !keepDraft) {
        clearMessage();
      }
    }, [isNewSession, initialMessage]);

    const { clearPreferredTool } = toolConfiguration;
    const preferredToolId = effectiveChatPreferredToolId({
      requestedToolId: toolConfiguration.preferredToolId,
      agent: activeAgent,
      plugins: memberPlugins ?? [],
    });
    const { isLoading: isLoadingProjects } = useProjects();
    const activeProject = useActiveProject();

    // Search and file tools require indexing. Spreadsheet Analysis reads the
    // uploaded bytes directly as soon as the upload succeeds.
    const hasPendingFiles = useMemo(
      () => !spreadsheetPilot && currentMessageFiles.some((file) => isFilePending(file.status)),
      [currentMessageFiles, spreadsheetPilot]
    );

    // Convert ProjectFile to MinimalNortPoleDocument format for viewing
    const handleFileClick = useCallback(
      (file: ProjectFile) => {
        if (!setPresentingDocument) return;

        const documentForViewer: MinimalNortPoleDocument = {
          document_id: `project_file__${file.file_id}`,
          semantic_identifier: file.name,
        };

        setPresentingDocument(documentForViewer);
      },
      [setPresentingDocument]
    );

    const handleUploadChange = useCallback(
      async (e: React.ChangeEvent<HTMLInputElement>) => {
        const files = e.target.files;
        if (!files || files.length === 0) return;
        handleFileUpload(Array.from(files));
        e.target.value = "";
      },
      [handleFileUpload]
    );

    const prevChatStateRef = useRef(chatState);
    const prevRenderCompleteRef = useRef(latestMessageRenderComplete);

    useEffect(() => {
      // "Ready" requires the backend to be idle AND the previous answer
      // to have finished drawing on screen. Without the render-complete
      // gate, a queued follow-up fires while the smooth-streaming
      // typewriter is still flushing the prior answer.
      const wasReady =
        prevChatStateRef.current === "input" && prevRenderCompleteRef.current;
      const isReady =
        chatState === "input" &&
        latestMessageRenderComplete &&
        !queuedMessagesPaused;

      prevChatStateRef.current = chatState;
      prevRenderCompleteRef.current = latestMessageRenderComplete;

      if (!wasReady && isReady && queuedMessages.length > 0) {
        const nextMessage = queuedMessages[0]!;
        isAutoSending.current = true;
        stopTTS();
        if (nextMessage.selections?.length) {
          onSubmit(nextMessage.text, nextMessage.selections);
        } else {
          onSubmit(nextMessage.text);
        }
        isAutoSending.current = false;
        removeCurrentQueuedMessage(0);
      }
    }, [
      chatState,
      latestMessageRenderComplete,
      queuedMessages,
      queuedMessagesPaused,
      removeCurrentQueuedMessage,
      stopTTS,
      onSubmit,
    ]);

    // Animate attached files wrapper to its content height so CSS transitions
    // can interpolate between concrete pixel values (0px ↔ Npx).
    const showFiles = !isSearchMode && currentMessageFiles.length > 0;
    useEffect(() => {
      const wrapper = filesWrapperRef.current;
      const content = filesContentRef.current;
      if (!wrapper || !content) return;

      if (showFiles) {
        // Measure the inner content's actual height, then add padding (p-1 = 8px total)
        const PADDING = 8;
        wrapper.style.height = `${content.offsetHeight + PADDING}px`;
      } else {
        wrapper.style.height = "0px";
      }
    }, [showFiles, currentMessageFiles]);

    function handlePaste(event: React.ClipboardEvent) {
      if (disabled) return;
      const pastedFiles = getPastedFilesIfNoText(event.clipboardData);
      if (!previewOnly && pastedFiles.length > 0) {
        event.preventDefault();
        handleFileUpload(pastedFiles);
        return;
      }

      event.preventDefault();
      const text = event.clipboardData.getData("text/plain");
      if (!text) return;

      pasteText(text);
    }

    const handleRemoveMessageFile = useCallback(
      (fileId: string) => {
        setCurrentMessageFiles((prev) => prev.filter((f) => f.id !== fileId));
      },
      [setCurrentMessageFiles]
    );

    const { activePromptShortcuts } = usePromptShortcuts();
    // The list itself belongs to ToolsPopover, which reads it directly; only
    // the loading flag is wanted here, to hold the controls back.
    const { isLoading: sourcesLoading } = useAvailableSources();

    // Bottom controls are hidden until all data is loaded
    const controlsLoading =
      sourcesLoading || !activeAgent || llmManager.isLoadingProviders;
    const [showPrompts, setShowPrompts] = useState(false);

    const [tabbingIconIndex, setTabbingIconIndex] = useState(0);

    const hidePrompts = useCallback(() => {
      setTimeout(() => {
        setShowPrompts(false);
      }, 50);
      setTabbingIconIndex(0);
    }, []);

    function updateInputPrompt(prompt: InputPrompt) {
      hidePrompts();
      setMessage(prompt.content);
    }

    const { filtered: filteredPrompts, setQuery: setPromptFilterQuery } =
      useFilter(activePromptShortcuts, (prompt) => prompt.prompt);

    // Memoize sorted prompts to avoid re-sorting on every render
    const sortedFilteredPrompts = useMemo(
      () => [...filteredPrompts].sort((a, b) => a.id - b.id),
      [filteredPrompts]
    );

    // Reset tabbingIconIndex when filtered prompts change to avoid out-of-bounds
    useEffect(() => {
      setTabbingIconIndex(0);
    }, [filteredPrompts]);

    const handleContentEditableInput = useCallback(
      (event: React.SyntheticEvent<HTMLDivElement>) => {
        const text = handleInput(event);
        if (text.startsWith("/")) {
          setShowPrompts(true);
          setPromptFilterQuery(text.slice(1));
        } else {
          hidePrompts();
          setPromptFilterQuery("");
        }
      },
      [handleInput, hidePrompts, setPromptFilterQuery]
    );

    const shouldCompactImages = useMemo(() => {
      return currentMessageFiles.length > 1;
    }, [currentMessageFiles]);

    // Check if the agent has search tools available (internal search or web search)
    // AND if deep research is globally enabled in admin settings
    const showDeepResearch = useMemo(() => {
      const deepResearchGloballyEnabled =
        combinedSettingsData?.deep_research_enabled ?? true;

      // Resolved from the chat, not the URL. `projectId` is dropped once a chat
      // opens (`PARAMS_TO_SKIP` in `app/app/services/lib.tsx`), so a project
      // chat carries no project context in its URL — reading the search param
      // hid the toggle on the project page and left it showing in the one place
      // it actually breaks.
      // Loading counts as "unknown", and unknown withholds: an unloaded
      // projects list makes a project chat look like a normal one.
      const isProjectWorkflow = isLoadingProjects || activeProject !== null;

      // TODO(@yuhong): Re-enable Deep Research in Projects workflow once it is fully supported.
      // https://linear.app/nortpole-app/issue/ENG-3818/re-enable-deep-research-in-projects
      return (
        !isProjectWorkflow &&
        deepResearchGloballyEnabled &&
        hasSearchToolsAvailable(activeAgent?.tools || [])
      );
    }, [
      activeAgent?.tools,
      combinedSettingsData?.deep_research_enabled,
      activeProject,
      isLoadingProjects,
    ]);

    function handleKeyDownForPromptShortcuts(
      e: React.KeyboardEvent<HTMLDivElement>
    ) {
      if (!user?.preferences?.shortcut_enabled || !showPrompts) return;

      if (e.key === "Enter") {
        e.preventDefault();
        if (tabbingIconIndex === sortedFilteredPrompts.length) {
          // "Create a new prompt" is selected
          window.open("/app/settings/chat-preferences", "_self");
        } else {
          const selectedPrompt = sortedFilteredPrompts[tabbingIconIndex];
          if (selectedPrompt) {
            updateInputPrompt(selectedPrompt);
          }
        }
      } else if (e.key === "Tab" && e.shiftKey) {
        // Shift+Tab: cycle backward
        e.preventDefault();
        setTabbingIconIndex((prev) => Math.max(prev - 1, 0));
      } else if (e.key === "Tab") {
        // Tab: cycle forward
        e.preventDefault();
        setTabbingIconIndex((prev) =>
          Math.min(prev + 1, sortedFilteredPrompts.length)
        );
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        setTabbingIconIndex((prev) =>
          Math.min(prev + 1, sortedFilteredPrompts.length)
        );
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setTabbingIconIndex((prev) => Math.max(prev - 1, 0));
      }
    }

    const selectionChips = !isSearchMode && Boolean(selections?.length) && (
      <div className="flex flex-wrap gap-1.5 px-2 py-1.5">
        {selections?.map((item) => (
          <ActionButton
            key={`${item.kind}:${item.id}`}
            type="button"
            aria-label={quickAddCopy("remove", { name: item.label })}
            className="inline-flex max-w-full items-center gap-1.5 rounded-lg border border-border-01 px-2 py-1 text-xs text-text-04 hover:bg-background-neutral-01"
            onClick={() => toggleSelection(item)}
          >
            <span className="truncate">{item.label}</span>
            <SvgX aria-hidden="true" className="size-3 shrink-0" />
          </ActionButton>
        ))}
      </div>
    );

    const fileMenuLabel = showQuickAdd
      ? quickAddCopy("label")
      : t("appInputBar.attachFilesButton.tooltip");
    const chatControls = (
      <div
        {...(isSearchMode ? { inert: true } : {})}
        className={cn(
          "flex justify-between items-center w-full",
          isSearchMode
            ? "opacity-0 p-0 h-0 overflow-hidden pointer-events-none"
            : "opacity-100 p-1 h-11 pointer-events-auto",
          "transition-all duration-150"
        )}
      >
        {/* Bottom left controls */}
        {!previewOnly && <div className="flex flex-row items-center">
          {/* (+) button - always visible */}
          <FilePickerPopover
            onFileClick={handleFileClick}
            onPickRecent={(file: ProjectFile) => {
              // Check if file with same ID already exists
              if (
                !currentMessageFiles.some(
                  (existingFile) => existingFile.file_id === file.file_id
                )
              ) {
                setCurrentMessageFiles((prev) => [...prev, file]);
              }
            }}
            onUnpickRecent={(file: ProjectFile) => {
              setCurrentMessageFiles((prev) =>
                prev.filter(
                  (existingFile) => existingFile.file_id !== file.file_id
                )
              );
            }}
            handleUploadChange={handleUploadChange}
            trigger={(open) => (
              <Button
                disabled={disabled}
                icon={showQuickAdd ? SvgPlus : SvgPaperclip}
                tooltip={fileMenuLabel}
                aria-label={fileMenuLabel}
                interaction={open ? "hover" : "rest"}
                prominence="tertiary"
              />
            )}
            selectedFileIds={currentMessageFiles.map((f) => f.id)}
            leadingItems={quickAddItems}
            menuLabel={showQuickAdd ? quickAddCopy("label") : undefined}
            uploadLabel={showQuickAdd ? quickAddCopy("localFiles") : undefined}
          />

          {/* Controls that load in when data is ready */}
          <div
            data-testid="actions-container"
            className={cn(
              "flex flex-row items-center",
              controlsLoading && "invisible"
            )}
          >
            {activeAgent && (
              // Keyed, so switching agents starts clean rather than carrying
              // the previous agent's open panel and search term across.
              <ToolsPopover
                key={activeAgent.id}
                agent={activeAgent}
                toolConfiguration={toolConfiguration}
                disabled={disabled}
                composerIntegrations={
                  showQuickAdd ? { hasSelection, toggleSelection } : undefined
                }
              />
            )}
            {onToggleTabReading ? (
              <SelectButton
                disabled={disabled}
                icon={SvgGlobe}
                onClick={onToggleTabReading}
                state={tabReadingEnabled ? "selected" : "empty"}
              >
                {tabReadingEnabled
                  ? currentTabUrl
                    ? (() => {
                        try {
                          return new URL(currentTabUrl).hostname;
                        } catch {
                          return currentTabUrl;
                        }
                      })()
                    : t("appInputBar.tabReadingButton.readingLabel")
                  : t("appInputBar.tabReadingButton.readLabel")}
              </SelectButton>
            ) : (
              showDeepResearch && (
                <SelectButton
                  disabled={disabled || isMultiModelActive}
                  variant="select-light"
                  icon={SvgHourglass}
                  onClick={toggleDeepResearch}
                  state={deepResearchEnabled ? "selected" : "empty"}
                  foldable={!deepResearchEnabled}
                  tooltip={
                    isMultiModelActive
                      ? t("appInputBar.deepResearchButton.disabledTooltip")
                      : undefined
                  }
                >
                  {t("appInputBar.deepResearchButton.label")}
                </SelectButton>
              )
            )}

            {!isSearchMode && !controlsLoading && activeAgent && (
              <MCPConnectionPrompt
                key={`mcp-auth-${activeAgent.id}`}
                isStreaming={chatState === "streaming"}
                agent={activeAgent}
                toolConfiguration={toolConfiguration}
                disabled={disabled}
                onConnectionsClosed={() => inputRef.current?.focus()}
              />
            )}

            {(() => {
              if (!activeAgent || preferredToolId === null) return null;
              const tool = activeAgent.tools.find(
                (tool) => tool.id === preferredToolId
              );
              if (!tool) return null;
              return (
                <Disabled disabled={disabled}>
                  <SelectButton
                    variant="select-light"
                    icon={getIconForAction(tool)}
                    onClick={clearPreferredTool}
                    state="selected"
                  >
                    {tool.display_name}
                  </SelectButton>
                </Disabled>
              );
            })()}
          </div>
        </div>}

        {/* Bottom right controls */}
        <div className="flex flex-row items-center gap-1">
          {!previewOnly && modelComparison && !requiredModelId && !isSearchMode && (
            <Disabled disabled={disabled || chatState !== "input"}>
              <MultiModelSelector
                compactSingle
                selectedModels={modelComparison.selectedModels}
                onAdd={modelComparison.addModel}
                onRemove={modelComparison.removeModel}
                onReplace={modelComparison.replaceModel}
                requiresImageInput={llmManager.imageFilesPresent}
                modelBlockedReason={modelBlockedReason}
              />
            </Disabled>
          )}
          {!previewOnly && llmManager.chatModelMode && !isMultiModelActive && (
            requiredModelId ? (
              <Popover>
                <Popover.Trigger asChild>
                  <Button
                    icon={SvgSettings}
                    aria-label={t("appInputBar.modelSettings.label")}
                    prominence="tertiary"
                  />
                </Popover.Trigger>
                <Popover.Content side="top" align="end">
                  <div className="flex flex-col gap-2 p-3">
                    <Text>{modelLabel || t("appInputBar.modelSettings.unavailable")}</Text>
                    <Text>{t("appInputBar.modelSettings.required")}</Text>
                  </div>
                </Popover.Content>
              </Popover>
            ) : (
              <ModelSelector
                agentId={activeAgent?.id}
                value={
                  llmManager.chatModelMode === "manual"
                    ? (llmManager.currentLlm.modelConfigurationId ?? null)
                    : null
                }
                includeAutomatic
                modelBlockedReason={modelBlockedReason}
                requiresImageInput={llmManager.imageFilesPresent}
                disabled={disabled || llmManager.isLoadingProviders}
                onChange={(option) => {
                  if (option.modelConfigurationId == null) {
                    llmManager.resetChatModel?.();
                  } else {
                    llmManager.updateCurrentLlm(option);
                  }
                }}
                renderTrigger={() => (
                  <Button
                    icon={SvgSettings}
                    prominence="tertiary"
                    disabled={disabled || llmManager.isLoadingProviders}
                    aria-label={t("appInputBar.modelSettings.label")}
                    tooltip={t("appInputBar.modelSettings.current", {
                      model:
                        llmManager.chatModelMode === "auto"
                          ? t("appInputBar.modelSettings.auto")
                          : (modelLabel || t("appInputBar.modelSettings.unavailable")),
                    })}
                  />
                )}
              />
            )
          )}
          {!previewOnly && sttEnabled && ttsEnabled && (
            <Button
              icon={SvgAudio}
              prominence={voiceModeEnabled ? "primary" : "tertiary"}
              aria-pressed={voiceModeEnabled ?? false}
              aria-label={t("appInputBar.voiceMode.label")}
              tooltip={t(
                voiceModeEnabled ? "appInputBar.voiceMode.on" : "appInputBar.voiceMode.off"
              )}
              disabled={disabled}
              onClick={() => {
                if (voiceModeEnabled) {
                  stopTTS({ manual: true });
                  void stopRecordingRef.current?.();
                }
                setVoiceModeEnabled(!voiceModeEnabled);
              }}
            />
          )}
          {!previewOnly && showMicButton &&
            (sttEnabled ? (
              <MicrophoneButton
                onTranscription={(text) => setMessage(text)}
                disabled={disabled || chatState === "streaming"}
                autoSend={voiceModeEnabled || (user?.preferences?.voice_auto_send ?? false)}
                autoListen={
                  voiceModeEnabled || (user?.preferences?.voice_auto_playback ?? false)
                }
                isNewSession={isNewSession}
                chatState={chatState}
                onRecordingChange={handleRecordingChange}
                stopRecordingRef={stopRecordingRef}
                currentMessage={message}
                onRecordingStart={() => {}}
                onAutoSend={(text) => {
                  submitMessage(text);
                }}
                onMuteChange={setIsMuted}
                setMutedRef={setMutedRef}
                onAudioLevel={setAudioLevel}
              />
            ) : (
              <Button
                disabled
                icon={SvgMicrophone}
                aria-label={t("appInputBar.voiceSetupButton.ariaLabel")}
                prominence="tertiary"
                tooltip={t("appInputBar.voiceSetupButton.tooltip")}
              />
            ))}

          <Button
            disabled={
              chatState === "cancelling" ||
              (isCheckingCompletion && chatState === "unconfirmed") ||
              (chatState === "input" &&
                !isVoicePlaybackControllable &&
                (!message || missingPilotInputs)) ||
              (chatState === "streaming" && Boolean(message.trim()) && missingReportInputs) ||
              hasPendingFiles ||
              isClassifying
            }
            tooltip={
              chatState === "cancelling"
                ? t("appInputBar.sendButton.stoppingLabel")
                : hasPendingFiles
                  ? t("appInputBar.sendButton.processingFilesTooltip")
                  : missingReportInputs ? reportingCopy("required")
                    : missingSpreadsheet ? spreadsheetCopy("attach") : undefined
            }
            id="nortpole-chat-input-send-button"
            aria-label={
              chatState === "unconfirmed"
                ? t("appInputBar.sendButton.reloadLabel")
                : chatState === "cancelling"
                  ? t("appInputBar.sendButton.stoppingLabel")
                  : chatState !== "input" && message.trim() && !spreadsheetPilot
                    ? t("appInputBar.sendButton.sendLabel")
                    : canStopGeneration || isVoicePlaybackControllable
                      ? t("appInputBar.sendButton.stopLabel")
                      : t("appInputBar.sendButton.sendLabel")
            }
            icon={
              isCheckingCompletion && chatState === "unconfirmed"
                ? IconLoader
                : chatState === "unconfirmed"
                  ? SvgRefreshCw
                  : isClassifying || chatState === "cancelling"
                    ? IconLoader
                    : chatState !== "input" && message.trim() && !spreadsheetPilot
                      ? SvgArrowUp
                      : canStopGeneration || isVoicePlaybackControllable
                        ? SvgStop
                        : SvgArrowUp
            }
            onClick={() => {
              if (chatState === "unconfirmed") {
                const store = useChatSessionStore.getState();
                const sessionId = store.currentSessionId;
                const session = sessionId
                  ? store.sessions.get(sessionId)
                  : undefined;
                if (!sessionId || !session || isCheckingCompletion) return;
                setCheckingSessions((pending) =>
                  new Set(pending).add(sessionId)
                );
                void settleChatSession({
                  sessionId,
                  controller: session.abortController,
                  errorMessage: tReadiness("checkFailed"),
                  mode: "recovery",
                }).finally(() =>
                  setCheckingSessions((pending) => {
                    const remaining = new Set(pending);
                    remaining.delete(sessionId);
                    return remaining;
                  })
                );
                return;
              }
              const canSubmitNormally = chatState === "input";
              if (!canSubmitNormally && message.trim() && !spreadsheetPilot) {
                if (!missingReportInputs && queuedMessages.length < MAX_QUEUED_MESSAGES) {
                  enqueueWithSelections();
                  clearMessage();
                  // Drop the draft now; a reload could outrace the debounced
                  // empty-save.
                  clearChatDraft();
                }
              } else if (canStopGeneration) {
                stopTTS({ manual: true });
                stopGenerating();
              } else if (isVoicePlaybackControllable) {
                stopTTS({ manual: true });
              } else if (message) {
                submitMessage(message);
              }
            }}
          >
            {chatState === "cancelling"
              ? t("appInputBar.sendButton.stoppingLabel")
              : chatState === "unconfirmed"
                ? t("appInputBar.sendButton.reloadLabel")
                : undefined}
          </Button>
        </div>
      </div>
    );

    return (
      <>
        <QueuedMessageBar
          messages={queuedMessages}
          highlightedIndex={queueNav.highlightedIndex}
          onDiscard={removeCurrentQueuedMessage}
          onHighlight={queueNav.setHighlightedIndex}
        />
        <Disabled disabled={disabled} allowClick>
          <div
            ref={containerRef}
            id="nortpole-chat-input"
            className={cn(
              "relative w-full flex flex-col shadow-box-01 bg-background-neutral-00 rounded-16"
              // # Note (from @raunakab):
              //
              // `shadow-box-01` extends ~14px below the element (2px offset + 12px blur).
              // Because the content area in `Root` (app-layouts.tsx) uses `overflow-auto`,
              // shadows that exceed the container bounds are clipped.
              //
              // The 14px breathing room is now applied externally via animated spacer
              // divs in `AppPage.tsx` (above and below the AppInputBar) so that the
              // spacing can transition smoothly when switching between search and chat
              // modes. See the corresponding note there for details.
            )}
          >
            {(contextPickers || showRoutePicker) && (
              <div
                className={cn(
                  "flex flex-wrap items-center gap-1 border-b border-border-01 px-2 py-1",
                  isRecording && "hidden"
                )}
              >
                {contextPickers}
                {showRoutePicker && (
                  <RoutePicker
                    llmManager={llmManager}
                    requiredModelId={requiredModelId}
                    applyDefault={isNewSession}
                    disabled={disabled || isRecording || chatState !== "input"}
                  />
                )}
              </div>
            )}
            {activeReview?.kind === "expense-review" && (
              <ExpenseReviewForm
                libraries={libraries}
                files={currentMessageFiles}
                initialLibrary={activeReview.library}
                initialTitle={activeReview.option}
                disabled={disabled || chatState !== "input" || isRecording || isVoicePlaybackActive}
                onUpload={handleFileUpload}
                onCancel={() => setReview(null)}
                onRun={(library, policyTitle) => submitReview("expense-review", library, policyTitle)}
              />
            )}
            {activeReview?.kind === "document-review" && (
              <DocumentReviewForm
                libraries={libraries}
                packs={reviewPacks}
                files={currentMessageFiles}
                initialLibrary={activeReview.library}
                initialPack={activeReview.option}
                disabled={disabled || chatState !== "input" || isRecording || isVoicePlaybackActive}
                onUpload={handleFileUpload}
                onCancel={() => setReview(null)}
                onRun={(library, pack) => submitReview("document-review", library, pack)}
              />
            )}
            {/* Voice waveform overlay (positioned outside normal flow to avoid resizing input) */}
            {isTTSActuallySpeaking ? (
              <div className="absolute bottom-full mb-1 start-1 z-10">
                <Waveform
                  variant="speaking"
                  isActive={isTTSActuallySpeaking}
                  isMuted={isTTSMuted}
                  onMuteToggle={toggleTTSMute}
                />
              </div>
            ) : isRecording &&
              !isVoicePlaybackActive &&
              !shouldShowRecordingWaveformBelow ? (
              <div className="absolute bottom-full mb-1 start-1 end-1 z-10">
                <Waveform
                  variant="recording"
                  isActive={isRecording}
                  isMuted={isMuted}
                  audioLevel={audioLevel}
                  onMuteToggle={() => {
                    setMutedRef.current?.(!isMuted);
                  }}
                />
              </div>
            ) : null}

            {/* Attached Files */}
            <div
              ref={filesWrapperRef}
              {...(!showFiles ? { inert: true } : {})}
              className={cn(
                "transition-all duration-150",
                showFiles
                  ? "opacity-100 p-1"
                  : "opacity-0 p-0 overflow-hidden pointer-events-none"
              )}
            >
              <div ref={filesContentRef} className="flex flex-wrap gap-1">
                {currentMessageFiles.map((file) => (
                  <FileCard
                    key={file.id}
                    file={file}
                    removeFile={handleRemoveMessageFile}
                    onFileClick={handleFileClick}
                    compactImages={shouldCompactImages}
                  />
                ))}
              </div>
            </div>

            <div className="flex flex-row items-center w-full">
              <Popover
                open={user?.preferences?.shortcut_enabled && showPrompts}
                onOpenChange={setShowPrompts}
              >
                <Popover.Anchor asChild>
                  <div
                    ref={inputWrapperRef}
                    className={cn("px-3 py-2 flex-1 flex overflow-hidden", meetingPilot ? "h-28" : "h-11")}
                  >
                    <div
                      ref={inputRef}
                      id="nortpole-chat-input-textbox"
                      role="textbox"
                      aria-label={meetingPilot ? meetingCopy("placeholder") : t("appInputBar.input.ariaLabel")}
                      contentEditable={!disabled}
                      // Direction follows what the user types. While empty
                      // it follows the placeholder so its punctuation sits
                      // on the correct side in every locale.
                      dir={
                        message
                          ? "auto"
                          : (firstStrongTextDir(activePlaceholder) ?? "auto")
                      }
                      suppressContentEditableWarning
                      onPaste={handlePaste}
                      onCopy={handleCopy}
                      onCut={handleCut}
                      onMouseDown={handleTileMouseDown}
                      onClick={handleTileClick}
                      onBlur={() => queueNav.setHighlightedIndex(null)}
                      onKeyDownCapture={handleKeyDownForPromptShortcuts}
                      onInput={handleContentEditableInput}
                      onCompositionStart={handleCompositionStart}
                      onCompositionEnd={handleCompositionEnd}
                      className="p-[2px] w-full h-full outline-hidden bg-transparent whitespace-pre-wrap wrap-break-word overflow-y-auto"
                      tabIndex={disabled ? -1 : 0}
                      style={{
                        scrollbarWidth: "thin",
                        scrollbarColor: "var(--border-02) transparent",
                      }}
                      aria-multiline={true}
                      aria-disabled={disabled}
                      aria-placeholder={activePlaceholder}
                      data-placeholder={activePlaceholder}
                      data-empty={!message ? "" : undefined}
                      onKeyDown={(event) => {
                        if (
                          handleInputNavKeys(event, queueNav, handleTileKeyDown)
                        )
                          return;

                        // Enter to submit or queue (Shift+Enter falls through
                        // to browser default: inserts <br>).
                        if (
                          event.key === "Enter" &&
                          !showPrompts &&
                          !event.shiftKey &&
                          !event.nativeEvent.isComposing
                        ) {
                          event.preventDefault();
                          const canSubmitNormally = chatState === "input";
                          if (canSubmitNormally) {
                            if (
                              message &&
                              !disabled &&
                              !isClassifying &&
                              !hasPendingFiles
                            ) {
                              submitMessage(message);
                            }
                          } else if (
                            chatState !== "cancelling" &&
                            chatState !== "unconfirmed" &&
                            message.trim() &&
                            !disabled &&
                            !isClassifying &&
                            !hasPendingFiles &&
                            !spreadsheetPilot &&
                            !missingReportInputs &&
                            queuedMessages.length < MAX_QUEUED_MESSAGES
                          ) {
                            enqueueWithSelections();
                            clearMessage();
                            // Drop the draft now; a reload could outrace the
                            // debounced empty-save.
                            clearChatDraft();
                          }
                        }
                      }}
                    />
                  </div>
                </Popover.Anchor>

                <Popover.Content
                  side="top"
                  align="start"
                  onOpenAutoFocus={(e) => e.preventDefault()}
                  width={70}
                >
                  <Popover.Menu>
                    {[
                      ...sortedFilteredPrompts.map((prompt, index) => (
                        <LineItemButton
                          font="main-ui-action"
                          rounding={2}
                          key={prompt.id}
                          state={
                            tabbingIconIndex === index ? "selected" : "empty"
                          }
                          selectVariant={
                            tabbingIconIndex === index
                              ? "select-heavy"
                              : "select-light"
                          }
                          description={prompt.content?.trim()}
                          onClick={() => updateInputPrompt(prompt)}
                          title={prompt.prompt}
                        />
                      )),
                      sortedFilteredPrompts.length > 0 ? null : undefined,
                      <LineItemButton
                        font="main-ui-action"
                        rounding={2}
                        key="create-new"
                        {...navigation.linkTo("/app/settings/chat-preferences")}
                        icon={SvgPlus}
                        state={
                          tabbingIconIndex === sortedFilteredPrompts.length
                            ? "selected"
                            : "empty"
                        }
                        selectVariant={
                          tabbingIconIndex === sortedFilteredPrompts.length
                            ? "select-heavy"
                            : "select-light"
                        }
                        title={t("appInputBar.createPromptItem.title")}
                      />,
                    ]}
                  </Popover.Menu>
                </Popover.Content>
              </Popover>

              {isSearchMode && (
                <Section flexDirection="row" width="fit" gap={0}>
                  <Button
                    disabled={!message || isClassifying}
                    icon={SvgX}
                    onClick={() => clearMessage()}
                    prominence="tertiary"
                  />
                  <Button
                    disabled={
                      !message ||
                      isClassifying ||
                      hasPendingFiles ||
                      chatState === "cancelling" ||
                      chatState === "unconfirmed"
                    }
                    id="nortpole-chat-input-send-button"
                    aria-label={t("appInputBar.sendButton.sendLabel")}
                    icon={isClassifying ? IconLoader : SvgSearch}
                    onClick={() => {
                      if (chatState == "streaming") {
                        stopGenerating();
                      } else if (message) {
                        submitMessage(message);
                      }
                    }}
                    prominence="tertiary"
                  />
                  <Spacer orientation="horizontal" rem={0.25} />
                </Section>
              )}
            </div>

            {agentPilot?.kind === "document-analysis" && (
              <PilotDocumentPicker key={selectionScope} libraries={agentPilot.libraries} selected={pilotDocuments}
                onToggle={toggleSelection} disabled={disabled || chatState !== "input"} />
            )}
            {reporting && (
              <ReportingInputs libraries={reporting.libraries}
                value={report ?? { start: "", end: "", libraryIds: [] }}
                onChange={(value) => setReportSelection({ scope: selectionScope, value })}
                disabled={disabled || chatState !== "input"} />
            )}
            {spreadsheetPilot && (
              <fieldset disabled={disabled || chatState !== "input" || currentMessageFiles.length > 0}
                className="rounded-lg border border-border-01 px-3 py-2 text-sm">
                <label className="flex flex-col gap-1">
                  {spreadsheetCopy("attach")}
                  <NativeInput type="file" accept=".csv,.xlsx" className="text-text-04"
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      event.target.value = "";
                      if (!file) return;
                      if (!/\.(csv|xlsx)$/i.test(file.name) || file.size > 1024 * 1024) {
                        setSpreadsheetError(spreadsheetCopy("invalidFile"));
                        return;
                      }
                      setSpreadsheetError(null);
                      void handleFileUpload([file]);
                      if (!message.trim()) setMessage(spreadsheetCopy("prompt"));
                    }} />
                </label>
                {spreadsheetError && <p role="alert" className="text-status-text-error-05">{spreadsheetError}</p>}
              </fieldset>
            )}
            {selectionChips}
            {chatControls}

            {/* First recording cycle waveform below input */}
            {shouldShowRecordingWaveformBelow && (
              <div className="absolute top-full mt-1 start-1 end-1 z-10">
                <Waveform
                  variant="recording"
                  isActive={isRecording}
                  isMuted={isMuted}
                  audioLevel={audioLevel}
                  onMuteToggle={() => {
                    setMutedRef.current?.(!isMuted);
                  }}
                />
              </div>
            )}
            {tilePopover && (
              <PasteTilePopover
                text={tilePopover.text}
                tileElement={tilePopover.tile}
                onDismiss={dismissTilePopover}
                onTextChange={updateTileText}
                onExpand={() => expandTile(tilePopover.tile)}
              />
            )}
          </div>
        </Disabled>
        {/* Stays for the whole session: the warning is most relevant
            once the user is actually chatting. */}
        {incognitoEnabled && (
          <Section
            flexDirection="column"
            alignItems="center"
            height="fit"
            gap={0.125}
            className="mt-3 text-center"
          >
            <Text font="secondary-body" color="text-02">
              {t("appInputBar.incognitoNotice.text")}
            </Text>
            <Text font="secondary-body" color="text-02">
              {t("appInputBar.incognitoPolicyNotice.text")}
            </Text>
          </Section>
        )}
      </>
    );
  }
);
AppInputBar.displayName = "AppInputBar";

export default AppInputBar;
