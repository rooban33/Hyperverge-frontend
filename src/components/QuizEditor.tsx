"use client";

import "@blocknote/core/fonts/inter.css";
import "@blocknote/mantine/style.css";
import { useState, useEffect, useRef, useCallback, useMemo, forwardRef, useImperativeHandle } from "react";
import { ChevronLeft, ChevronRight, Plus, FileText, Trash2, FileCode, AudioLines, Check, HelpCircle, X, ChevronDown, Pen, ClipboardCheck, Search, BookOpen } from "lucide-react";

// Add custom styles for dark mode
import "./editor-styles.css";

// Import the BlockNoteEditor component
import BlockNoteEditor from "./BlockNoteEditor";
// Import the LearnerQuizView component
import LearnerQuizView from "./LearnerQuizView";
import ConfirmationDialog from "./ConfirmationDialog";
// Import the new Dropdown component
import Dropdown, { DropdownOption } from "./Dropdown";
// Import the ScorecardPickerDialog component
import ScorecardPickerDialog, { CriterionData, ScorecardTemplate } from "./ScorecardPickerDialog";
// Import the new Scorecard component
import Scorecard, { ScorecardHandle } from "./Scorecard";
// Import dropdown options
import { questionTypeOptions, answerTypeOptions, codingLanguageOptions } from "./dropdownOptions";
// Import quiz types
import { QuizEditorHandle, QuizQuestionConfig, QuizQuestion, QuizEditorProps, APIQuestionResponse, ScorecardCriterion } from "../types";
// Add import for LearningMaterialLinker
import LearningMaterialLinker from "./LearningMaterialLinker";
// Import Toast component
import Toast from "./Toast";
// Import Tooltip component
import Tooltip from "./Tooltip";
// Import the PublishConfirmationDialog component
import PublishConfirmationDialog from './PublishConfirmationDialog';

// Default configuration for new questions
const defaultQuestionConfig: QuizQuestionConfig = {
    inputType: 'text',
    responseType: 'chat',
    questionType: 'objective',
    knowledgeBaseBlocks: [],
    linkedMaterialIds: []
};

// Add these new interfaces after your existing interfaces
interface LearningMaterial {
    id: number;
    title: string;
    type: string;
    status: string;
}

// Helper function to extract text from all blocks in a BlockNote document
export const extractTextFromBlocks = (blocks: any[]): string => {
    if (!blocks || blocks.length === 0) return "";

    return blocks.map(block => {
        // Handle different block types
        if (block.type === "paragraph") {
            // For paragraph blocks, extract text content
            return block.content ? block.content.map((item: any) =>
                typeof item === 'string' ? item : (item.text || "")
            ).join("") : "";
        } else if (block.type === "heading") {
            // For heading blocks, extract text content
            return block.content ? block.content.map((item: any) =>
                typeof item === 'string' ? item : (item.text || "")
            ).join("") : "";
        } else if (block.type === "bulletListItem" || block.type === "numberedListItem" || block.type === "checkListItem") {
            // For list items, extract text content
            return block.content ? block.content.map((item: any) =>
                typeof item === 'string' ? item : (item.text || "")
            ).join("") : "";
        } else if (block.type === "codeBlock") {
            // For code blocks, extract text content from content array
            return block.content ? block.content.map((item: any) =>
                typeof item === 'string' ? item : (item.text || "")
            ).join("") : "";
        } else if (block.text) {
            // Fallback for blocks with direct text property
            return block.text;
        }
        return "";
    }).join("\n").trim();
};

/**
 * Extracts and formats knowledge base content for API calls.
 * Validates that blocks contain actual content, not just empty structures.
 * 
 * @param {QuizQuestionConfig} config - The question configuration containing knowledge base data
 * @returns {Object|null} - Formatted knowledge base data for API or null if no valid content
 */
export const getKnowledgeBaseContent = (config: QuizQuestionConfig) => {
    // Check for knowledgeBaseBlocks
    const knowledgeBaseBlocks = config.knowledgeBaseBlocks || [];
    const linkedMaterialIds = config.linkedMaterialIds || [];

    // Extract text from blocks to check if they contain actual content
    const hasNonEmptyBlocks = knowledgeBaseBlocks.length > 0 &&
        extractTextFromBlocks(knowledgeBaseBlocks).trim().length > 0;

    // Check if there are any linked materials
    const hasLinkedMaterials = linkedMaterialIds.length > 0;

    // If we have either valid blocks or linked materials, return the knowledge base data
    if (hasNonEmptyBlocks || hasLinkedMaterials) {
        return {
            blocks: hasNonEmptyBlocks ? knowledgeBaseBlocks : [],
            linkedMaterialIds: hasLinkedMaterials ? linkedMaterialIds : []
        };
    }

    // If no valid knowledge base content, return null
    return null;
};

const QuizEditor = forwardRef<QuizEditorHandle, QuizEditorProps>(({
    initialQuestions = [], // Not used anymore - kept for backward compatibility
    onChange,
    isDarkMode = true,
    className = "",
    isPreviewMode = false,
    readOnly = false,
    onPublish,
    taskId,
    status = 'draft',
    onPublishSuccess,
    showPublishConfirmation = false,
    onPublishCancel,
    isEditMode = false,
    onSaveSuccess,
    taskType = 'quiz',
    currentQuestionId,
    onQuestionChange,
    onSubmitAnswer,
    userId,
    schoolId, // Add schoolId prop to access school scorecards
    onValidationError,
    courseId,
    scheduledPublishAt = null,
}, ref) => {
    // For published quizzes/exams: data is always fetched from the API
    // For draft quizzes/exams: always start with empty questions
    // initialQuestions prop is no longer used

    // Initialize questions state - always start with empty array
    const [questions, setQuestions] = useState<QuizQuestion[]>([]);
    // Store the original data for cancel functionality
    const originalQuestionsRef = useRef<QuizQuestion[]>([]);
    // Add a ref to store the original title
    const originalTitleRef = useRef<string>("");

    // Add loading state for fetching questions
    const [isLoadingQuestions, setIsLoadingQuestions] = useState(true);
    // Track if data has been fetched to prevent infinite loops
    const [hasFetchedData, setHasFetchedData] = useState(false);

    // Add state for school scorecards
    const [schoolScorecards, setSchoolScorecards] = useState<ScorecardTemplate[]>([]);
    // Add loading state for fetching scorecards
    const [isLoadingScorecards, setIsLoadingScorecards] = useState(false);

    // Add toast state
    const [showToast, setShowToast] = useState(false);
    const [toastTitle, setToastTitle] = useState("");
    const [toastMessage, setToastMessage] = useState("");
    const [toastEmoji, setToastEmoji] = useState("🚀");

    // Add useEffect to automatically hide toast after 5 seconds
    useEffect(() => {
        if (showToast) {
            const timer = setTimeout(() => {
                setShowToast(false);
            }, 5000);

            // Cleanup the timer when component unmounts or showToast changes
            return () => clearTimeout(timer);
        }
    }, [showToast]);

    // Make sure we reset questions when component mounts for draft quizzes
    useEffect(() => {
        if (status === 'draft') {
            console.log('Initializing empty questions array for draft quiz');
            setQuestions([]);
        }
    }, [status]);

    // Fetch school scorecards when component mounts for draft quizzes
    useEffect(() => {
        const fetchSchoolScorecards = async () => {
            if (schoolId) {
                setIsLoadingScorecards(true);
                try {
                    const response = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}/scorecards/?org_id=${schoolId}`);
                    if (!response.ok) {
                        throw new Error('Failed to fetch school scorecards');
                    }

                    const data = await response.json();

                    // Transform the API response to ScorecardTemplate format
                    if (data && Array.isArray(data)) {
                        const transformedScorecards = data.map(scorecard => ({
                            id: scorecard.id,
                            name: scorecard.title,
                            icon: <FileText size={16} className="text-white" />,
                            is_template: false, // Not a hard-coded template
                            new: false, // Not newly created in this session
                            criteria: scorecard.criteria.map((criterion: ScorecardCriterion) => ({
                                name: criterion.name,
                                description: criterion.description,
                                maxScore: criterion.max_score,
                                minScore: criterion.min_score
                            })) || []
                        }));

                        setSchoolScorecards(transformedScorecards);

                        // Now that we have the scorecards, fetch the questions
                        await fetchQuestions(transformedScorecards);
                    } else {
                        // If no scorecard data, fetch questions with empty scorecards
                        await fetchQuestions();
                    }
                } catch (error) {
                    console.error('Error fetching school scorecards:', error);
                } finally {
                    setIsLoadingScorecards(false);
                }
            } else {
                // If no schoolId, just fetch questions with empty scorecards
                await fetchQuestions();
            }
        };

        // Define the fetchQuestions function that takes scorecards as a parameter
        const fetchQuestions = async (availableScorecards: ScorecardTemplate[] = []) => {
            // Only fetch if we have a taskId, the status is published, and we haven't already fetched
            if (taskId && !hasFetchedData) {
                try {
                    const response = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}/tasks/${taskId}`);
                    if (!response.ok) {
                        throw new Error('Failed to fetch task details');
                    }

                    const data = await response.json();

                    // Update the questions with the fetched data
                    if (data && data.questions && data.questions.length > 0) {
                        const updatedQuestions = data.questions.map((question: APIQuestionResponse) => {
                            // Map API question type to local questionType
                            const questionType = question.type;

                            // Use answer blocks directly from the API if available,
                            // otherwise create a default paragraph block
                            const correctAnswer = (question.answer ? question.answer : [
                                {
                                    type: "paragraph",
                                    content: [
                                        {
                                            type: "text",
                                            text: question.answer || "",
                                            styles: {}
                                        }
                                    ]
                                }
                            ]);

                            // Handle scorecard data if scorecard_id is present
                            let scorecardData = undefined;
                            if (question.scorecard_id && availableScorecards.length > 0) {
                                // Find matching scorecard from school scorecards
                                const matchingScorecard = availableScorecards.find(sc => parseInt(sc.id) === question.scorecard_id);

                                if (matchingScorecard) {
                                    console.log(`Found matching scorecard for question ${question.id}: ${matchingScorecard.name}`);
                                    scorecardData = {
                                        id: matchingScorecard.id,
                                        name: matchingScorecard.name,
                                        criteria: matchingScorecard.criteria.map(criterion => ({
                                            ...criterion,
                                            minScore: criterion.minScore
                                        })),
                                    };
                                }
                            }

                            // Extract knowledgeBaseBlocks and linkedMaterialIds from context if it exists
                            let knowledgeBaseBlocks: any[] = [];
                            let linkedMaterialIds: string[] = [];

                            if (question.context) {
                                // Extract blocks for knowledge base if they exist
                                if (question.context.blocks && Array.isArray(question.context.blocks)) {
                                    knowledgeBaseBlocks = question.context.blocks;
                                }

                                // Extract linkedMaterialIds if they exist
                                if (question.context.linkedMaterialIds && Array.isArray(question.context.linkedMaterialIds)) {
                                    linkedMaterialIds = question.context.linkedMaterialIds;
                                }
                            }

                            return {
                                id: String(question.id),
                                content: question.blocks || [],
                                config: {
                                    inputType: question.input_type || 'text' as 'text' | 'code' | 'audio',
                                    responseType: question.response_type,
                                    correctAnswer: correctAnswer,
                                    questionType: questionType as 'objective' | 'subjective' | 'coding',
                                    scorecardData: scorecardData,
                                    knowledgeBaseBlocks: knowledgeBaseBlocks,
                                    linkedMaterialIds: linkedMaterialIds,
                                    codingLanguages: question.coding_languages || []
                                }
                            };
                        });

                        // Update questions state
                        setQuestions(updatedQuestions);

                        // Notify parent component about the update, but only once and after our state is updated
                        if (onChange) {
                            // Use setTimeout to break the current render cycle
                            setTimeout(() => {
                                onChange(updatedQuestions);
                            }, 0);
                        }

                        // Store the original data for cancel operation
                        originalQuestionsRef.current = JSON.parse(JSON.stringify(updatedQuestions));
                    }

                    // Mark that we've fetched the data - do this regardless of whether questions were found
                    setHasFetchedData(true);
                } catch (error) {
                    console.error('Error fetching quiz questions:', error);
                    // Even on error, mark as fetched to prevent infinite retry loops
                    setHasFetchedData(true);
                } finally {
                    setIsLoadingQuestions(false);
                }
            } else {
                setIsLoadingQuestions(false);
            }
        };

        fetchSchoolScorecards();
    }, [taskId, status]);

    // Reset hasFetchedData when taskId changes
    useEffect(() => {
        setHasFetchedData(false);
    }, [taskId]);

    // Cleanup effect - clear questions when component unmounts or taskId changes
    useEffect(() => {
        // Return cleanup function
        return () => {
            // Clear questions state and refs when component unmounts
            setQuestions([]);
            originalQuestionsRef.current = [];
        };
    }, [taskId]);

    // Store the original title when it changes in the dialog (for cancel operation)
    useEffect(() => {
        const dialogTitleElement = document.querySelector('.dialog-content-editor')?.parentElement?.querySelector('h2');
        if (dialogTitleElement) {
            originalTitleRef.current = dialogTitleElement.textContent || "";
        }
    }, []);

    // Current question index
    const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);

    // Internal state to track the current question ID for preview mode
    const [activeQuestionId, setActiveQuestionId] = useState<string | undefined>(() => {
        // Initialize with currentQuestionId if provided, otherwise use first question id if questions exist
        if (currentQuestionId) {
            return currentQuestionId;
        }
        return questions.length > 0 ? questions[0]?.id : undefined;
    });

    // Update current question index when currentQuestionId changes
    useEffect(() => {
        if (currentQuestionId && questions.length > 0) {
            const index = questions.findIndex(q => q.id === currentQuestionId);
            if (index !== -1) {
                setCurrentQuestionIndex(index);
            }
        }
    }, [currentQuestionId, questions]);

    // Update activeQuestionId when currentQuestionIndex changes in preview mode
    useEffect(() => {
        if (questions.length > 0 && currentQuestionIndex >= 0 && currentQuestionIndex < questions.length) {
            const newActiveId = questions[currentQuestionIndex].id;
            setActiveQuestionId(newActiveId);
        }
    }, [currentQuestionIndex, questions]);

    // State to track if a new question was just added (for animation)
    const [newQuestionAdded, setNewQuestionAdded] = useState(false);

    // State for delete confirmation
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
    // Add state for scorecard delete confirmation
    const [showScorecardDeleteConfirm, setShowScorecardDeleteConfirm] = useState(false);

    // State for tracking publishing status
    const [isPublishing, setIsPublishing] = useState(false);

    // State for tracking publishing errors
    const [publishError, setPublishError] = useState<string | null>(null);

    // Reference to the current BlockNote editor instance
    const editorRef = useRef<any>(null);

    // Use ref to track the last edit to prevent unnecessary updates
    const lastContentUpdateRef = useRef<string>("");

    // Reference to the correct answer editor
    const correctAnswerEditorRef = useRef<any>(null);

    // Reference to the knowledge base editor
    const knowledgeBaseEditorRef = useRef<any>(null);

    // State for scorecard templates dialog
    const [showScorecardDialog, setShowScorecardDialog] = useState(false);
    const [scorecardDialogPosition, setScorecardDialogPosition] = useState<{ top: number, left: number } | null>(null);
    const scorecardButtonRef = useRef<HTMLButtonElement>(null);

    // We don't need the hasScorecard state anymore since we're using currentQuestionConfig.scorecardData
    // If needed for the scorecard title, we'll keep that state
    const [scorecardTitle, setScorecardTitle] = useState<string>("Scorecard");

    // Reference to the scorecard component
    const scorecardRef = useRef<ScorecardHandle>(null);

    // State for tracking active tab (question or answer)
    const [activeEditorTab, setActiveEditorTab] = useState<'question' | 'answer' | 'scorecard' | 'knowledge'>('question');

    // State to track which field is being highlighted for validation errors
    const [highlightedField, setHighlightedField] = useState<'question' | 'answer' | 'codingLanguage' | null>(null);

    // Add validation utility functions to reduce duplication
    // These functions can validate both the current question and any question by index

    /**
     * Highlights a field (question or answer) to draw attention to a validation error
     * @param field The field to highlight
     */
    const highlightField = useCallback((field: 'question' | 'answer' | 'codingLanguage') => {
        // Set the highlighted field
        setHighlightedField(field);

        // Clear the highlight after 4 seconds
        setTimeout(() => {
            setHighlightedField(null);
        }, 4000);
    }, []);

    /**
     * Validates if question content is non-empty
     * @param content The content blocks to validate
     * @returns True if content has non-empty text or contains media blocks, false otherwise
     */
    const validateQuestionContent = useCallback((content: any[]) => {
        if (!content || content.length === 0) {
            return false;
        }

        // Check for text content
        const textContent = extractTextFromBlocks(content);
        if (textContent.trim().length > 0) {
            return true;
        }

        // If no text content, check if there are any media blocks (image, audio, video)
        const hasMediaBlocks = content.some(block =>
            block.type === 'image' ||
            block.type === 'audio' ||
            block.type === 'video'
        );

        return hasMediaBlocks;
    }, []);

    /**
     * Validates if a question has a non-empty correct answer
     * @param questionConfig The question configuration containing the answer
     * @returns True if correct answer exists and is non-empty, false otherwise
     */
    const validateCorrectAnswer = useCallback((questionConfig: QuizQuestionConfig) => {
        if (questionConfig.correctAnswer && questionConfig.correctAnswer.length > 0) {
            const textContent = extractTextFromBlocks(questionConfig.correctAnswer);
            return textContent.trim().length > 0;
        }
        return false;
    }, []);

    /**
     * Validates if a question has a valid scorecard attached
     * @param questionConfig The question configuration containing the scorecard data
     * @returns True if a valid scorecard with criteria exists, false otherwise
     */
    const validateScorecard = useCallback((questionConfig: QuizQuestionConfig) => {
        return !!(questionConfig.scorecardData &&
            questionConfig.scorecardData.criteria &&
            questionConfig.scorecardData.criteria.length > 0);
    }, []);

    /**
     * Validates scorecard criteria for empty names and descriptions
     * @param scorecard The scorecard data to validate
     * @param callbacks Object containing callback functions for validation actions
     * @returns True if all criteria are valid, false if any validation fails
     */
    const validateScorecardCriteria = (
        scorecard: ScorecardTemplate | undefined,
        callbacks: {
            setActiveTab: (tab: 'question' | 'answer' | 'scorecard' | 'knowledge') => void;
            showErrorMessage?: (title: string, message: string, emoji?: string) => void;
            questionIndex?: number; // Optional for showing question number in error message
        }
    ): boolean => {
        // If no scorecard or not a user-created scorecard (new), return true (valid)
        if (!scorecard || !scorecard.new) {
            return true;
        }

        const { setActiveTab, showErrorMessage, questionIndex } = callbacks;

        // Check each criterion for empty name or description
        for (let i = 0; i < scorecard.criteria.length; i++) {
            const criterion = scorecard.criteria[i];

            // Check for empty name
            if (!criterion.name || criterion.name.trim() === '') {
                // Switch to scorecard tab first
                setActiveTab('scorecard');

                // Use a self-invoking function for delayed highlight and error message
                (function (index) {
                    setTimeout(() => {
                        // Create event to highlight the problematic row
                        const event = new CustomEvent('highlight-criterion', {
                            detail: {
                                index,
                                field: 'name'
                            }
                        });
                        document.dispatchEvent(event);

                        // Show error message if callback is provided
                        if (showErrorMessage) {
                            const suffix = questionIndex !== undefined ? ` for question ${questionIndex + 1}` : '';
                            showErrorMessage(
                                "Empty Scorecard Parameter",
                                `Please provide a name for parameter ${index + 1} in the scorecard${suffix}`,
                                "🚫"
                            );
                        }
                    }, 250);
                })(i);

                return false;
            }

            // Check for empty description
            if (!criterion.description || criterion.description.trim() === '') {
                // Switch to scorecard tab first
                setActiveTab('scorecard');

                // Use a self-invoking function for delayed highlight and error message
                (function (index, name) {
                    setTimeout(() => {
                        // Create event to highlight the problematic row
                        const event = new CustomEvent('highlight-criterion', {
                            detail: {
                                index,
                                field: 'description'
                            }
                        });
                        document.dispatchEvent(event);

                        // Show error message if callback is provided
                        if (showErrorMessage) {
                            const suffix = questionIndex !== undefined ? ` for question ${questionIndex + 1}` : '';
                            showErrorMessage(
                                "Empty Scorecard Parameter",
                                `Please provide a description for parameter ${index + 1} in the scorecard${suffix}`,
                                "🚫"
                            );
                        }
                    }, 250);
                })(i, criterion.name);

                return false;
            }
        }

        // If all criteria passed validation
        return true;
    };

    /**
     * Validates all questions in the quiz/exam and navigates to the first invalid question
     * @returns True if all questions are valid, false otherwise
     */
    const validateAllQuestions = useCallback(() => {
        // Check if there are any questions
        if (questions.length === 0) {
            if (onValidationError) {
                onValidationError(
                    "No Questions",
                    "Please add at least one question before publishing"
                );
            }
            return false;
        }

        // Validate all questions
        for (let i = 0; i < questions.length; i++) {
            const question = questions[i];

            // Check if question has content
            if (!validateQuestionContent(question.content)) {
                // Navigate to the question with missing content
                setCurrentQuestionIndex(i);
                setActiveEditorTab('question');

                // Highlight the question field
                highlightField('question');

                // Notify parent about validation error
                if (onValidationError) {
                    onValidationError(
                        "Empty Question",
                        `Question ${i + 1} is empty. Please add details to the question`
                    );
                }
                return false;
            }


            // For coding questions, check if coding languages are set
            if (question.config.questionType === 'coding') {
                if (!question.config.codingLanguages || !Array.isArray(question.config.codingLanguages) || question.config.codingLanguages.length === 0) {
                    // Navigate to the question with missing coding languages
                    setCurrentQuestionIndex(i);

                    // Highlight the coding language field
                    highlightField('codingLanguage');

                    // Notify parent about validation error
                    if (onValidationError) {
                        onValidationError(
                            "Missing Coding Languages",
                            `Question ${i + 1} does not have any programming language selected`
                        );
                    }
                    return false;
                } else {
                    console.log("question.config.codingLanguages is not empty");
                }
            }

            // For objective questions, check if correct answer is set
            if (question.config.questionType === 'objective' || question.config.questionType === 'coding') {
                if (!validateCorrectAnswer(question.config)) {
                    // Navigate to the question with missing answer
                    setCurrentQuestionIndex(i);
                    setActiveEditorTab('answer');

                    // Highlight the answer field
                    highlightField('answer');

                    // Notify parent about validation error
                    if (onValidationError) {
                        onValidationError(
                            "Empty Correct Answer",
                            `Question ${i + 1} has no correct answer. Please add a correct answer`
                        );
                    }
                    return false;
                }
            }

            // For subjective questions, check if scorecard is set
            if (question.config.questionType === 'subjective') {
                if (!validateScorecard(question.config)) {
                    // Navigate to the question with missing scorecard
                    setCurrentQuestionIndex(i);
                    setActiveEditorTab('scorecard');

                    // Notify parent about validation error
                    if (onValidationError) {
                        onValidationError(
                            "Missing Scorecard",
                            `Question ${i + 1} has no scorecard. Please add a scorecard for evaluating the answer`
                        );
                    }
                    return false;
                }

                // Check for empty criterion names or descriptions in the scorecard
                if (question.config.scorecardData) {
                    // Navigate to the question with the problematic scorecard first
                    setCurrentQuestionIndex(i);

                    // Use the shared validation function for scorecards
                    const isValid = validateScorecardCriteria(
                        question.config.scorecardData,
                        {
                            setActiveTab: setActiveEditorTab,
                            showErrorMessage: onValidationError,
                            questionIndex: i
                        }
                    );

                    if (!isValid) {
                        return false;
                    }
                }
            }
        }

        return true;
    }, [questions, onValidationError, validateQuestionContent, validateCorrectAnswer, validateScorecard, setCurrentQuestionIndex, setActiveEditorTab, validateScorecardCriteria, highlightField]);

    // Function to handle opening the scorecard templates dialog
    const handleOpenScorecardDialog = () => {
        const buttonElement = scorecardButtonRef.current;
        if (buttonElement) {
            const rect = buttonElement.getBoundingClientRect();

            // Approximate height of the dialog (templates + header)
            const estimatedDialogHeight = 350;

            // Position the bottom of the dialog above the button with some spacing
            setScorecardDialogPosition({
                top: Math.max(10, rect.top - estimatedDialogHeight - 10), // Ensure at least 10px from top of viewport
                left: Math.max(10, rect.left - 120) // Center horizontally but ensure it's not off-screen
            });
            setShowScorecardDialog(true);
        }
    };

    // Function to handle creating a new scorecard
    const handleCreateNewScorecard = () => {
        setShowScorecardDialog(false);

        // Set the scorecard title
        setScorecardTitle("New Scorecard");

        // Create an empty scorecard
        const newScorecardData: ScorecardTemplate = {
            id: crypto.randomUUID(), // Generate a unique UUID for the scorecard
            name: "New Scorecard",
            new: true, // Mark as newly created in this session
            is_template: false, // Not a template
            criteria: [
                { name: '', description: '', minScore: 1, maxScore: 5 }
            ]
        };

        // Add the new scorecard to the question's config
        handleConfigChange({
            scorecardData: newScorecardData
        });

        // Update school scorecards state with new scorecard
        const updatedScorecards = [...schoolScorecards, newScorecardData];
        setSchoolScorecards(updatedScorecards);

        // Switch to the scorecard tab
        setActiveEditorTab('scorecard');

        // Focus on the scorecard title after a short delay to allow rendering
        setTimeout(() => {
            scorecardRef.current?.focusName();
        }, 100);
    };

    // Function to handle selecting a scorecard template
    const handleSelectScorecardTemplate = (template: ScorecardTemplate) => {
        setShowScorecardDialog(false);

        // Set the scorecard title
        setScorecardTitle(template.name || "Scorecard Template");

        let scorecard: ScorecardTemplate;

        if (template.is_template) {
            // one of the hardcoded templates
            scorecard = {
                id: crypto.randomUUID(),
                name: template.name,
                new: true,
                is_template: false,
                criteria: template.criteria,
            };
        } else {
            // one of the user generated scorecards - could be both published scorecards or newly created scorecards
            // in this session itself
            scorecard = {
                id: template.id,
                name: template.name,
                new: false,
                is_template: false,
                criteria: template.criteria,
            };
        }

        // Update school scorecards state with new scorecard
        if (scorecard.new) {
            const updatedScorecards = [...schoolScorecards, scorecard];
            setSchoolScorecards(updatedScorecards);
        }

        // Add the scorecard data to the question's config
        handleConfigChange({
            scorecardData: scorecard
        });

        // Switch to the scorecard tab
        setActiveEditorTab('scorecard');

        // Focus on the scorecard title after a short delay to allow rendering
        if (scorecard.new) {
            setTimeout(() => {
                scorecardRef.current?.focusName();
            }, 100);
        }
    };

    // Function to set the editor reference
    const setEditorInstance = useCallback((editor: any) => {
        editorRef.current = editor;
    }, []);

    // Memoize the current question content and config to prevent unnecessary re-renders
    const currentQuestion = useMemo(() =>
        questions[currentQuestionIndex] || { content: [], config: defaultQuestionConfig },
        [questions, currentQuestionIndex]);

    const currentQuestionContent = useMemo(() =>
        currentQuestion.content || [],
        [currentQuestion]);

    const currentQuestionConfig = useMemo(() =>
        currentQuestion.config || defaultQuestionConfig,
        [currentQuestion]);

    // Function to set the correct answer editor reference
    const setCorrectAnswerEditorInstance = useCallback((editor: any) => {
        correctAnswerEditorRef.current = editor;
    }, []);

    // Function to set the knowledge base editor reference
    const setKnowledgeBaseEditorInstance = useCallback((editor: any) => {
        knowledgeBaseEditorRef.current = editor;
    }, []);

    // Handle content change for the current question - use useCallback to memoize
    const handleQuestionContentChange = useCallback((content: any[]) => {
        if (questions.length === 0) return;

        // Simply update the content without all the complexity
        const updatedQuestions = [...questions];
        updatedQuestions[currentQuestionIndex] = {
            ...updatedQuestions[currentQuestionIndex],
            content
        };

        // Update state
        setQuestions(updatedQuestions);

        // Call onChange callback if provided
        if (onChange) {
            onChange(updatedQuestions);
        }
    }, [questions, currentQuestionIndex, onChange]);

    // Handle correct answer content change
    const handleCorrectAnswerChange = useCallback((content: any[]) => {
        if (questions.length === 0) return;

        // Store blocks but don't extract text on every change
        const updatedQuestions = [...questions];
        updatedQuestions[currentQuestionIndex] = {
            ...updatedQuestions[currentQuestionIndex],
            config: {
                ...updatedQuestions[currentQuestionIndex].config,
                correctAnswer: content
            }
        };
        setQuestions(updatedQuestions);

        if (onChange) {
            onChange(updatedQuestions);
        }
    }, [questions, currentQuestionIndex, onChange]);

    // Handle configuration change for the current question
    const handleConfigChange = useCallback((configUpdate: Partial<QuizQuestionConfig>, options?: { updateTemplate?: boolean, newQuestionType?: 'objective' | 'subjective' | 'coding' }) => {
        if (questions.length === 0) return;

        const updatedQuestions = [...questions];
        updatedQuestions[currentQuestionIndex] = {
            ...updatedQuestions[currentQuestionIndex],
            config: {
                ...updatedQuestions[currentQuestionIndex].config,
                ...configUpdate
            }
        };

        // If updateTemplate flag is true and we have a newQuestionType, update the template content
        if (options?.updateTemplate && options.newQuestionType && status === 'draft') {
            const currentContent = updatedQuestions[currentQuestionIndex].content || [];

            // Check if any block has an ID (indicating user modification)
            const hasUserModifiedContent = currentContent.some(block => 'id' in block);

            if (!hasUserModifiedContent) {
                // Generate new template blocks based on the new question type
                const newTemplateContent = getQuestionTemplateBlocks(options.newQuestionType);

                // Update the content with the new template
                updatedQuestions[currentQuestionIndex].content = newTemplateContent;
            }
        }

        setQuestions(updatedQuestions);

        if (onChange) {
            onChange(updatedQuestions);
        }
    }, [questions, currentQuestionIndex, onChange, status]);

    const removeScorecardFromSchoolScoreboards = useCallback(() => {
        let scorecardForQuestion = questions[currentQuestionIndex].config.scorecardData

        if (!scorecardForQuestion) {
            return;
        }

        if (scorecardForQuestion && scorecardForQuestion.new) {
            const updatedScorecards = schoolScorecards.filter(scorecard => scorecard.id !== scorecardForQuestion.id);
            setSchoolScorecards(updatedScorecards);
        }

        const updatedQuestions = [...questions];

        for (let i = 0; i < updatedQuestions.length; i++) {
            if (updatedQuestions[i].config.scorecardData && updatedQuestions[i].config.scorecardData?.id === scorecardForQuestion.id) {
                updatedQuestions[i].config.scorecardData = undefined;
            }
        }

        setQuestions(updatedQuestions);

        if (onChange) {
            onChange(updatedQuestions);
        }
    }, [questions, currentQuestionIndex, schoolScorecards, onChange]);

    // Function to get template blocks based on question type
    const getQuestionTemplateBlocks = (questionType: 'objective' | 'subjective' | 'coding') => {
        // Common blocks that appear in all templates
        const commonBlocks = [
            {
                type: "heading",
                props: { level: 2 },
                content: [{ "text": "Welcome to the Question Editor!", "type": "text", styles: {} }],
            },
            {
                type: "paragraph",
                content: [{ "text": "This is where you will create your question. You can modify this template or remove it to start from scratch.", "type": "text", styles: {} }]
            },
            {
                type: "paragraph",
                content: [{ "text": "", "type": "text", styles: {} }]
            },
            {
                type: "heading",
                props: { level: 3 },
                content: [{ "text": "Question Types", "type": "text", styles: {} }]
            },
            {
                type: "paragraph",
                content: [{ "text": "You can select from these question types:", "type": "text", styles: {} }]
            },
            {
                type: "bulletListItem",
                content: [{ "text": "Objective", "type": "text", styles: { "bold": true } }, { "text": ": For questions with specific correct answers (multiple choice, true/false, etc.)", "type": "text", styles: {} }]
            },
            {
                type: "bulletListItem",
                content: [{ "text": "Subjective", "type": "text", styles: { "bold": true } }, { "text": ": For questions that don't have a single correct answer.", "type": "text", styles: {} }]
            },
            {
                type: "bulletListItem",
                content: [{ "text": "Coding", "type": "text", styles: { "bold": true } }, { "text": ": For questions that require learners to write code as their answer", "type": "text", styles: {} }]
            },
            {
                type: "paragraph",
                content: [{ "text": "", "type": "text", styles: {} }]
            }
        ];

        // Answer type section - not shown for coding questions
        const answerTypeBlocks = questionType !== 'coding' ? [
            {
                type: "heading",
                props: { level: 3 },
                content: [{ "text": "Answer Types", "type": "text", styles: {} }]
            },
            {
                type: "paragraph",
                content: [{ "text": "You can select from these answer types:", "type": "text", styles: {} }]
            },
            {
                type: "bulletListItem",
                content: [{ "text": "Text", "type": "text", styles: { "bold": true } }, { "text": ": Learners need to type their answer", "type": "text", styles: {} }]
            },
            {
                type: "bulletListItem",
                content: [{ "text": "Audio", "type": "text", styles: { "bold": true } }, { "text": ": Learners need to record their answer", "type": "text", styles: {} }]
            },
            {
                type: "paragraph",
                content: [{ "text": "", "type": "text", styles: {} }]
            }
        ] : [];

        // Programming languages section - only shown for coding questions
        const programmingLanguagesBlocks = questionType === 'coding' ? [
            {
                type: "heading",
                props: { level: 3 },
                content: [{ "text": "Programming Languages", "type": "text", styles: {} }]
            },
            {
                type: "paragraph",
                content: [{ "text": "You should select the programming languages learners will use to answer the question. You can select multiple languages from the dropdown.", "type": "text", styles: {} }]
            },
            {
                type: "paragraph",
                content: [{ "text": "", "type": "text", styles: {} }]
            }
        ] : [];

        // Tabs explanation - dependent on question type
        let tabsExplanationBlocks = [];
        if (questionType === 'objective') {
            tabsExplanationBlocks = [
                {
                    type: "heading",
                    props: { level: 3 },
                    content: [{ "text": "Editor Tabs", "type": "text", styles: {} }]
                },
                {
                    type: "paragraph",
                    content: [{ "text": "The Question Editor has three tabs for this question type:", "type": "text", styles: {} }]
                },
                {
                    type: "bulletListItem",
                    content: [{ "text": "Question", "type": "text", styles: { "bold": true } }, { "text": ": (Current tab) Where you write the question text", "type": "text", styles: {} }]
                },
                {
                    type: "bulletListItem",
                    content: [{ "text": "Correct Answer", "type": "text", styles: { "bold": true } }, { "text": ": Where you provide the expected answer for automatic evaluation", "type": "text", styles: {} }]
                },
                {
                    type: "bulletListItem",
                    content: [{ "text": "AI Training", "type": "text", styles: { "bold": true } }, { "text": ": Where you can add knowledge base content to help AI evaluate learner responses", "type": "text", styles: {} }]
                }
            ];
        } else if (questionType === 'subjective') {
            tabsExplanationBlocks = [
                {
                    type: "heading",
                    props: { level: 3 },
                    content: [{ "text": "Editor Tabs", "type": "text", styles: {} }]
                },
                {
                    type: "paragraph",
                    content: [{ "text": "The Question Editor has three tabs for this question type:", "type": "text", styles: {} }]
                },
                {
                    type: "bulletListItem",
                    content: [{ "text": "Question", "type": "text", styles: { "bold": true } }, { "text": ": (Current tab) Where you write the question text", "type": "text", styles: {} }]
                },
                {
                    type: "bulletListItem",
                    content: [{ "text": "Scorecard", "type": "text", styles: { "bold": true } }, { "text": ": Where you define grading criteria for subjective responses", "type": "text", styles: {} }]
                },
                {
                    type: "bulletListItem",
                    content: [{ "text": "AI Training", "type": "text", styles: { "bold": true } }, { "text": ": Where you can add knowledge base content to help AI evaluate learner responses", "type": "text", styles: {} }]
                }
            ];
        } else { // coding
            tabsExplanationBlocks = [
                {
                    type: "heading",
                    props: { level: 3 },
                    content: [{ "text": "Editor Tabs", "type": "text", styles: {} }]
                },
                {
                    type: "paragraph",
                    content: [{ "text": "The Question Editor has three tabs for this question type:", "type": "text", styles: {} }]
                },
                {
                    type: "bulletListItem",
                    content: [{ "text": "Question", "type": "text", styles: { "bold": true } }, { "text": ": (Current tab) Where you write the question text", "type": "text", styles: {} }]
                },
                {
                    type: "bulletListItem",
                    content: [{ "text": "Correct Answer", "type": "text", styles: { "bold": true } }, { "text": ": Where you provide the expected code solution", "type": "text", styles: {} }]
                },
                {
                    type: "bulletListItem",
                    content: [{ "text": "AI Training", "type": "text", styles: { "bold": true } }, { "text": ": Where you can add knowledge base content to help AI evaluate learner code solutions", "type": "text", styles: {} }]
                }
            ];
        }

        // Available block types (from learning material editor)
        const blockTypesBlocks = [
            {
                type: "heading",
                props: { level: 3 },
                content: [{ "text": "Available Block Types", "type": "text", styles: {} }]
            },
            {
                type: "paragraph",
                content: [{ "text": "Here are some examples of the different types of blocks you can use:", "type": "text", styles: {} }]
            },
            {
                type: "heading",
                props: { level: 2 },
                content: [{ "text": "Headings (like this one)", "type": "text", styles: {} }]
            },
            {
                type: "bulletListItem",
                content: [{ "text": "Bullet lists (like this)", "type": "text", styles: {} }]
            },
            {
                type: "numberedListItem",
                content: [{ "text": "Numbered lists (like this)", "type": "text", styles: {} }]
            },
            {
                type: "checkListItem",
                content: [{ "text": "Check lists (like this)", "type": "text", styles: {} }]
            },
            {
                type: "paragraph",
                content: [{ "text": "Regular paragraphs for your main content", "type": "text", styles: {} }]
            },
            {
                type: "paragraph",
                content: [{ "text": "Insert images/videos/audio clips by clicking the + icon on the left and selecting Image/Video/Audio", "type": "text", styles: {} }]
            },
            {
                type: "paragraph",
                content: [{ "text": "Insert code blocks by clicking the + icon on the left and selecting Code Block", "type": "text", styles: {} }]
            },
            {
                type: "paragraph",
                content: [{ "text": "", "type": "text", styles: {} }]
            },
            {
                type: "heading",
                props: { level: 3 },
                content: [{ "text": "Creating Nested Content", "type": "text", styles: {} }]
            },
            {
                type: "paragraph",
                content: [{ "text": "You can create nested content in two ways:", "type": "text", styles: {} }]
            },
            {
                type: "bulletListItem",
                content: [{ "text": "Using the Tab key: Simply press Tab while your cursor is on a block to indent it", "type": "text", styles: {} }]
            },
            {
                type: "bulletListItem",
                content: [{ "text": "Using the side menu: Hover near the left edge of a block, click the menu icon (the button with 6 dots), and drag the block to the desired nested position inside another block", "type": "text", styles: {} }]
            },
            {
                type: "paragraph",
                content: [{ "text": "", "type": "text", styles: {} }]
            },
            {
                type: "paragraph",
                content: [{ "text": "Here is an example of a nested list:", "type": "text", styles: { "bold": true } }]
            },
            {
                type: "bulletListItem",
                content: [{ "text": "Main topic 1", "type": "text", styles: {} }],
                children: [
                    {
                        type: "bulletListItem",
                        props: { indent: 1 },
                        content: [{ "text": "Subtopic 1.1 (indented using Tab or side menu)", "type": "text", styles: {} }]
                    },
                    {
                        type: "bulletListItem",
                        props: { indent: 1 },
                        content: [{ "text": "Subtopic 1.2", "type": "text", styles: {} }],
                        children: [{
                            type: "bulletListItem",
                            props: { indent: 2 },
                            content: [{ "text": "Further nested item (press Tab again to create deeper nesting)", "type": "text", styles: {} }]
                        }]
                    },

                ]
            },
            {
                type: "paragraph",
                content: [{ "text": "", "type": "text", styles: {} }]
            },
        ];

        // Writing effective questions section
        const effectiveQuestionsBlocks = [
            {
                type: "heading",
                props: { level: 3 },
                content: [{ "text": "Writing Effective Questions", "type": "text", styles: {} }]
            },
            {
                type: "paragraph",
                content: [{ "text": "For best results:", "type": "text", styles: {} }]
            },
            {
                type: "bulletListItem",
                content: [{ "text": "Be clear and specific in your question text", "type": "text", styles: {} }]
            }
        ];

        // Question type specific tips
        let questionTypeTipsBlocks = [];
        if (questionType === 'subjective') {
            questionTypeTipsBlocks = [
                {
                    type: "bulletListItem",
                    content: [{ "text": "Create a detailed scorecard with clear evaluation criteria or pick one of the templates already provided", "type": "text", styles: {} }]
                }
            ];
        } else if (questionType === 'coding') {
            questionTypeTipsBlocks = [
                {
                    type: "bulletListItem",
                    content: [{ "text": "Provide a clear problem statement and any constraints or performance requirements", "type": "text", styles: {} }]
                }
            ];
        } else {
            questionTypeTipsBlocks = [
                {
                    type: "bulletListItem",
                    content: [{ "text": "Make sure your correct answer is complete and matches the expected format", "type": "text", styles: {} }]
                }
            ];
        }

        // Preview and publish explanation
        const previewPublishBlocks = [
            {
                type: "paragraph",
                content: [{ "text": "", "type": "text", styles: {} }]
            },
            {
                type: "heading",
                props: { level: 3 },
                content: [{ "text": "Preview and Publishing", "type": "text", styles: {} }]
            },
            {
                type: "paragraph",
                content: [{ "text": "When you're ready to test your quiz:", "type": "text", styles: {} }]
            },
            {
                type: "bulletListItem",
                content: [{ "text": "Preview Button", "type": "text", styles: { "bold": true } }, { "text": ": Lets you see and answer the question exactly as a learner will see it", "type": "text", styles: {} }]
            },
            {
                type: "bulletListItem",
                content: [{ "text": "Publish Button", "type": "text", styles: { "bold": true } }, { "text": ": Makes the quiz available to learners. You can always edit and publish again", "type": "text", styles: {} }]
            },
            {
                type: "paragraph",
                content: [{ "text": "", "type": "text", styles: {} }]
            },
            {
                type: "paragraph",
                content: [{ "text": "Delete this template when you are ready to create your own question!", "type": "text", styles: {} }]
            }
        ];

        // Combine all blocks based on question type
        return [
            ...commonBlocks,
            ...answerTypeBlocks,
            ...programmingLanguagesBlocks,
            ...tabsExplanationBlocks,
            {
                type: "paragraph",
                content: [{ "text": "", "type": "text", styles: {} }]
            },
            ...blockTypesBlocks,
            ...effectiveQuestionsBlocks,
            ...questionTypeTipsBlocks,
            ...previewPublishBlocks
        ];
    };

    // Add a new question
    const addQuestion = useCallback(() => {
        // Get the previous question's configuration if available
        // Otherwise, use default values
        let questionType = 'objective';
        let inputType: 'text' | 'code' | 'audio' = 'text';
        let codingLanguages: string[] = [];

        // If there's at least one question (to be used as a reference)
        if (questions.length > 0) {
            const previousQuestion = questions[questions.length - 1];
            if (previousQuestion && previousQuestion.config) {
                // Use the previous question's type
                questionType = previousQuestion.config.questionType;
                // Use the previous question's input type (answer type)
                inputType = previousQuestion.config.inputType;
                // Use the previous question's coding languages if available
                if (previousQuestion.config.codingLanguages &&
                    Array.isArray(previousQuestion.config.codingLanguages) &&
                    previousQuestion.config.codingLanguages.length > 0) {
                    codingLanguages = [...previousQuestion.config.codingLanguages];
                }
            }
        }

        const newQuestion: QuizQuestion = {
            id: `question-${Date.now()}`,
            content: getQuestionTemplateBlocks(questionType as 'objective' | 'subjective' | 'coding'),
            config: {
                ...defaultQuestionConfig,
                questionType: questionType as 'objective' | 'subjective' | 'coding',
                inputType: inputType,
                codingLanguages: codingLanguages
            }
        };

        const updatedQuestions = [...questions, newQuestion];
        setQuestions(updatedQuestions);
        setCurrentQuestionIndex(updatedQuestions.length - 1);

        // Reset last content update ref
        lastContentUpdateRef.current = "";

        // Trigger animation
        setNewQuestionAdded(true);

        // Reset animation flag after animation completes
        setTimeout(() => {
            setNewQuestionAdded(false);
        }, 800); // slightly longer than animation duration to ensure it completes

        if (onChange) {
            onChange(updatedQuestions);
        }

        setActiveEditorTab('question');

        // Removed slash menu opening after adding a new question
    }, [questions, onChange]);

    // Navigate to previous question
    const goToPreviousQuestion = useCallback(() => {
        if (currentQuestionIndex > 0) {
            // Reset last content update ref when navigating to a different question
            lastContentUpdateRef.current = "";
            const newIndex = currentQuestionIndex - 1;


            // Reset active tab to question when navigating
            // Only change active tab if the current tab is not available in the next question
            const nextQuestion = questions[newIndex];
            if (activeEditorTab === 'scorecard' && nextQuestion.config.questionType !== 'subjective') {
                setActiveEditorTab('question');
            } else if (activeEditorTab === 'answer' && nextQuestion.config.questionType == 'subjective') {
                setActiveEditorTab('question');
            }

            setCurrentQuestionIndex(newIndex);

            // Call the onQuestionChange callback if provided
            if (onQuestionChange && questions[newIndex] && !isPreviewMode) {
                onQuestionChange(questions[newIndex].id);
            }
        }
    }, [currentQuestionIndex, onQuestionChange, questions, activeEditorTab, isPreviewMode]);

    // Navigate to next question
    const goToNextQuestion = useCallback(() => {
        if (currentQuestionIndex < questions.length - 1) {
            // Reset last content update ref when navigating to a different question
            lastContentUpdateRef.current = "";
            const newIndex = currentQuestionIndex + 1;

            // Reset active tab to question when navigating
            const nextQuestion = questions[newIndex];
            if (activeEditorTab === 'scorecard' && nextQuestion.config.questionType !== 'subjective') {
                setActiveEditorTab('question');
            } else if (activeEditorTab === 'answer' && nextQuestion.config.questionType == 'subjective') {
                setActiveEditorTab('question');
            }

            setCurrentQuestionIndex(newIndex);

            // Call the onQuestionChange callback if provided
            if (onQuestionChange && questions[newIndex] && !isPreviewMode) {
                onQuestionChange(questions[newIndex].id);
            }
        }
    }, [currentQuestionIndex, questions.length, onQuestionChange, questions, activeEditorTab, isPreviewMode]);

    // Delete current question
    const deleteQuestion = useCallback(() => {
        if (questions.length <= 1) {
            // If only one question, just clear the questions array
            setQuestions([]);
            setShowDeleteConfirm(false);

            if (onChange) {
                onChange([]);
            }
            return;
        }

        const updatedQuestions = [...questions];
        updatedQuestions.splice(currentQuestionIndex, 1);

        setQuestions(updatedQuestions);

        // Adjust current index if necessary
        if (currentQuestionIndex >= updatedQuestions.length) {
            setCurrentQuestionIndex(updatedQuestions.length - 1);
        }

        if (onChange) {
            onChange(updatedQuestions);
        }

        // Hide confirmation dialog
        setShowDeleteConfirm(false);

        // Reset last content update ref when deleting a question
        lastContentUpdateRef.current = "";
    }, [questions, currentQuestionIndex, onChange]);

    // Effect to initialize lastContentUpdateRef when changing questions
    useEffect(() => {
        if (questions.length > 0) {
            lastContentUpdateRef.current = JSON.stringify(currentQuestionContent);
        }
    }, [currentQuestionIndex, questions.length, currentQuestionContent]);

    // Placeholder component for empty quiz
    const EmptyQuizPlaceholder = () => (
        <div className="flex flex-col items-center justify-center h-full w-full text-center p-8">
            <h3 className="text-xl font-light text-white mb-3">Questions are the gateway to learning</h3>
            <p className="text-gray-400 max-w-md mb-8">
                Add questions to create an interactive quiz for your learners
            </p>
            {status === 'draft' && (
                <button
                    onClick={addQuestion}
                    className="flex items-center px-5 py-2.5 text-sm text-black bg-white hover:bg-gray-100 rounded-md transition-colors cursor-pointer"
                    disabled={readOnly}
                >
                    <div className="w-5 h-5 rounded-full border border-black flex items-center justify-center mr-2">
                        <Plus size={12} className="text-black" />
                    </div>
                    Add Your First Question
                </button>
            )}
        </div>
    );

    // Handle publish confirmation
    const handleShowPublishConfirmation = () => {
        if (onPublish) {
            onPublish();
        }
    };

    const handleCancelPublish = () => {
        if (onPublishCancel) {
            onPublishCancel();
        }
    };

    // Modified handleConfirmPublish to accept scheduled_publish_at parameter
    const handleConfirmPublish = async (scheduledPublishAt?: string | null) => {
        if (!taskId) {
            console.error("Cannot publish: taskId is not provided");
            setPublishError("Cannot publish: Task ID is missing");
            return;
        }

        setIsPublishing(true);
        setPublishError(null);

        try {
            // Get the current title from the dialog - it may have been edited
            const dialogTitleElement = document.querySelector('.dialog-content-editor')?.parentElement?.querySelector('h2');
            const currentTitle = dialogTitleElement?.textContent || '';

            // Format questions for the API
            const formattedQuestions = questions.map((question) => {
                // Map questionType to API type
                const questionType = question.config.questionType;
                // Map inputType
                const inputType = question.config.inputType

                let scorecard = null
                let scorecardId = null

                if (question.config.scorecardData) {
                    // Use our helper function to determine if this is an API scorecard
                    const isExistingScorecard = isPublishedScorecard(question.config.scorecardData);

                    if (isExistingScorecard) {
                        scorecardId = question.config.scorecardData.id
                    } else {
                        scorecard = {
                            id: question.config.scorecardData.id,
                            title: question.config.scorecardData.name,
                            criteria: question.config.scorecardData.criteria.map(criterion => ({
                                name: criterion.name,
                                description: criterion.description,
                                min_score: criterion.minScore,
                                max_score: criterion.maxScore
                            }))
                        }
                    }
                }

                // Return the formatted question object for all questions, not just those with scorecards
                return {
                    blocks: question.content,
                    answer: question.config.correctAnswer || [],
                    input_type: inputType,
                    response_type: questionType === 'subjective' ? "report" : "chat",
                    coding_languages: question.config.codingLanguages || [],
                    generation_model: null,
                    type: questionType,
                    max_attempts: taskType === 'exam' ? 1 : null,
                    is_feedback_shown: taskType === 'exam' ? false : true,
                    scorecard: scorecard,
                    scorecard_id: scorecardId,
                    context: getKnowledgeBaseContent(question.config),
                };
            });

            console.log("Publishing quiz with title:", currentTitle);
            console.log("Formatted questions:", formattedQuestions);

            // Make POST request to publish the quiz
            const response = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}/tasks/${taskId}/quiz`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    title: currentTitle,
                    questions: formattedQuestions,
                    scheduled_publish_at: scheduledPublishAt
                }),
            });

            if (!response.ok) {
                throw new Error(`Failed to publish quiz: ${response.status}`);
            }

            // Get the updated task data from the response
            const updatedTaskData = await response.json();
            console.log("API response:", updatedTaskData);

            // Ensure the status is set to 'published'
            const publishedTaskData = {
                ...updatedTaskData,
                status: 'published',
                title: currentTitle,
                scheduled_publish_at: scheduledPublishAt,
                id: taskId // Ensure the ID is included for proper updating in the module list
            };

            console.log("Quiz published successfully", publishedTaskData);

            // Set publishing to false to avoid state updates during callbacks
            setIsPublishing(false);

            // Call the original onPublish callback if provided
            if (onPublish) {
                onPublish();
            }

            // Call the onPublishSuccess callback if provided
            if (onPublishSuccess) {
                // Use setTimeout to break the current render cycle
                setTimeout(() => {
                    onPublishSuccess(publishedTaskData);
                }, 0);
            }
        } catch (error) {
            console.error("Error publishing quiz:", error);
            setPublishError(error instanceof Error ? error.message : "Failed to publish quiz");
            setIsPublishing(false);
        }
    };

    // Modified handleSave for edit mode to send raw blocks of the correct answer
    const handleSave = async () => {
        if (!taskId) {
            console.error("Cannot save: taskId is not provided");
            return;
        }

        try {
            // Get the current title from the dialog - it may have been edited
            const dialogTitleElement = document.querySelector('.dialog-content-editor')?.parentElement?.querySelector('h2');
            const currentTitle = dialogTitleElement?.textContent || '';

            // Format questions for the API
            const formattedQuestions = questions.map((question) => {
                // Map questionType to API type
                const questionType = question.config.questionType;

                // Get input_type from the current config
                const inputType = question.config.inputType;
                console.log(`Question ${question.id} - Input type: ${inputType}`);

                return {
                    id: question.id,
                    blocks: question.content,
                    answer: question.config.correctAnswer || [],
                    coding_languages: question.config.codingLanguages || [],
                    type: questionType,
                    input_type: inputType,
                    context: getKnowledgeBaseContent(question.config)
                };
            });

            console.log("Saving quiz with formatted questions:", formattedQuestions);

            // Make PUT request to update the quiz content, keeping the same status
            const response = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}/tasks/${taskId}/quiz`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    title: currentTitle,
                    questions: formattedQuestions,
                    scheduled_publish_at: scheduledPublishAt
                }),
            });

            if (!response.ok) {
                throw new Error(`Failed to save quiz: ${response.status}`);
            }

            // Get the updated task data from the response
            const updatedTaskData = await response.json();

            // Create updated data with the current title
            const updatedData = {
                ...updatedTaskData,
                title: currentTitle,
                id: taskId,
            };

            console.log("Quiz saved successfully", updatedData);

            // Call the onSaveSuccess callback if provided
            if (onSaveSuccess) {
                setTimeout(() => {
                    onSaveSuccess(updatedData);
                }, 0);
            }
        } catch (error) {
            console.error("Error saving quiz:", error);
        }
    };

    // Handle cancel in edit mode - revert to original data
    const handleCancel = () => {
        if (originalQuestionsRef.current.length === 0) return;

        console.log('Original questions:', originalQuestionsRef.current);
        // Restore the original questions
        setQuestions(JSON.parse(JSON.stringify(originalQuestionsRef.current)));

        // Return the original title to the dialog header
        const dialogTitleElement = document.querySelector('.dialog-content-editor')?.parentElement?.querySelector('h2');
        if (dialogTitleElement && originalTitleRef.current) {
            dialogTitleElement.textContent = originalTitleRef.current;
        }
    };

    // Check if the current question has coding languages set
    const hasCodingLanguages = useCallback(() => {
        if (questions.length === 0 || currentQuestionIndex < 0 || currentQuestionIndex >= questions.length) {
            return false;
        }

        const question = questions[currentQuestionIndex];
        if (question.config.questionType !== 'coding') {
            return true; // Not relevant for non-coding questions
        }

        // Check if coding languages array exists and has at least one value
        return !!(question.config.codingLanguages &&
            Array.isArray(question.config.codingLanguages) &&
            question.config.codingLanguages.length > 0);
    }, [questions, currentQuestionIndex]);

    // Expose methods to parent component via the ref
    useImperativeHandle(ref, () => ({
        save: handleSave,
        cancel: handleCancel,
        hasContent: () => questions.length > 0,
        hasQuestionContent: () => {
            const isValid = validateQuestionContent(currentQuestionContent);
            if (!isValid) {
                // Switch to question tab
                setActiveEditorTab('question');
                // Highlight the question field to draw attention to the error
                highlightField('question');
            }
            return isValid;
        },
        getCurrentQuestionType: () => {
            // Return the current question's type, defaulting to 'objective' if not set
            return currentQuestionConfig.questionType;
        },
        hasCorrectAnswer: () => {
            const isValid = validateCorrectAnswer(currentQuestionConfig);
            if (!isValid) {
                // Switch to answer tab
                setActiveEditorTab('answer');
                // Highlight the answer field to draw attention to the error
                highlightField('answer');
            }
            return isValid;
        },
        hasScorecard: () => validateScorecard(currentQuestionConfig),
        hasCodingLanguages: () => {
            const isValid = hasCodingLanguages();
            if (!isValid) {
                // Highlight the coding language field to draw attention to the error
                highlightField('codingLanguage');
            }
            return isValid;
        },
        setActiveTab: (tab) => {
            // Set the active editor tab
            setActiveEditorTab(tab);
        },
        validateBeforePublish: validateAllQuestions,
        getCurrentQuestionConfig: () => {
            // Return the current question's configuration
            return currentQuestionConfig;
        },
        validateScorecardCriteria: (scorecard: ScorecardTemplate | undefined, callbacks: any) =>
            validateScorecardCriteria(scorecard, callbacks)
    }));

    // Update the MemoizedLearnerQuizView to include the correct answer
    const MemoizedLearnerQuizView = useMemo(() => {
        // No validation checks - directly use the questions array
        // Make a deep copy of questions
        let questionsWithCorrectAnswers = JSON.parse(JSON.stringify(questions));

        // Update the current question with the latest correct answer blocks if possible
        if (correctAnswerEditorRef.current && currentQuestionIndex >= 0 && currentQuestionIndex < questionsWithCorrectAnswers.length) {
            const currentCorrectAnswer = correctAnswerEditorRef.current.document || [];
            questionsWithCorrectAnswers[currentQuestionIndex].config = {
                ...questionsWithCorrectAnswers[currentQuestionIndex].config,
                correctAnswer: currentCorrectAnswer
            };
        }

        return (
            <LearnerQuizView
                questions={questionsWithCorrectAnswers}
                isDarkMode={isDarkMode}
                readOnly={readOnly}
                className="w-full h-full"
                onSubmitAnswer={onSubmitAnswer}
                taskType={taskType}
                currentQuestionId={activeQuestionId}
                onQuestionChange={(questionId) => {
                    // Find the index for this question ID
                    const index = questions.findIndex(q => q.id === questionId);
                    if (index !== -1) {
                        // Update our internal state
                        setCurrentQuestionIndex(index);
                    }
                }}
                userId={userId}
                isTestMode={true}
            />
        );
    }, [questions, isDarkMode, readOnly, onSubmitAnswer, taskType, activeQuestionId, userId, currentQuestionIndex]);

    // Define dropdown options
    // Now removed and imported from dropdownOptions.ts

    // Get dropdown option objects based on config values
    const getQuestionTypeOption = useCallback((type: string = 'objective') => {
        return questionTypeOptions.find(option => option.value === type) || questionTypeOptions[0];
    }, []);

    const getAnswerTypeOption = useCallback((type: string = 'text') => {
        return answerTypeOptions.find(option => option.value === type) || answerTypeOptions[0];
    }, []);

    // Handle question type change
    const handleQuestionTypeChange = useCallback((option: DropdownOption | DropdownOption[]) => {
        // We know this is a single-select dropdown
        if (!Array.isArray(option)) {
            setSelectedQuestionType(option);

            // Get the new question type
            const newQuestionType = option.value as 'objective' | 'subjective' | 'coding';

            // Update the question config with the new question type and also update template if needed
            handleConfigChange({
                questionType: newQuestionType,
                responseType: newQuestionType === 'subjective' ? 'report' : 'chat',
                inputType: newQuestionType === 'coding' ? 'text' : currentQuestionConfig.inputType
            }, {
                updateTemplate: true,
                newQuestionType: newQuestionType
            });

            // Set active tab to question whenever question type changes
            setActiveEditorTab('question');
        }
    }, [handleConfigChange, status, questions, currentQuestionIndex, onChange, currentQuestionConfig.inputType]);

    // Handle answer type change
    const handleAnswerTypeChange = useCallback((option: DropdownOption | DropdownOption[]) => {
        // We know this is a single-select dropdown
        if (!Array.isArray(option)) {
            setSelectedAnswerType(option);

            // Update the question config with the new input type
            handleConfigChange({
                inputType: option.value as 'text' | 'code' | 'audio'
            });

            // Ensure question state is updated immediately in case we save right after changing
            console.log(`Answer type changed to: ${option.value}`);
        }
    }, [handleConfigChange]);

    // Handle coding language change
    const handleCodingLanguageChange = useCallback((option: DropdownOption | DropdownOption[]) => {
        // Cast to array since we know this is a multiselect dropdown
        const selectedOptions = Array.isArray(option) ? option : [option];

        // Define exclusive languages
        const exclusiveLanguages = ['react', 'sql', 'python', 'nodejs'];

        // Validation logic for language combinations
        let validatedOptions = [...selectedOptions];
        let invalidMessage = "";

        // Find all exclusive languages in the selection
        const exclusiveSelectedLanguages = selectedOptions.filter(opt =>
            exclusiveLanguages.includes(opt.value)
        );

        // Check if any exclusive language is selected
        if (exclusiveSelectedLanguages.length > 0) {
            // If there are multiple exclusive languages, get the last one selected
            const lastExclusiveLanguage = exclusiveSelectedLanguages[exclusiveSelectedLanguages.length - 1];

            // If we have more than one language selected and at least one is exclusive,
            // we need to filter out all other languages
            if (selectedOptions.length > 1) {
                // Keep only the last exclusive language
                validatedOptions = [lastExclusiveLanguage];

                // Get a nice display name for the exclusive language
                const displayName = lastExclusiveLanguage.label

                invalidMessage = `${displayName} must be used alone. Other languages cannot be added along with it.`;
            }
        } else {
            // No exclusive languages, check for HTML and CSS combination
            const hasCSS = selectedOptions.some(opt => opt.value === 'css');
            const hasHTML = selectedOptions.some(opt => opt.value === 'html');

            if (hasCSS && !hasHTML) {
                // Find the HTML option in the coding language options
                const htmlOption = codingLanguageOptions.find(opt => opt.value === 'html');

                if (htmlOption) {
                    // Add HTML to the validated options
                    validatedOptions.push(htmlOption);
                    invalidMessage = "HTML has been automatically selected because CSS requires HTML";
                }
            }
        }

        // Set the validated options
        setSelectedCodingLanguages(validatedOptions);

        // Update the question config with the validated options
        handleConfigChange({
            codingLanguages: validatedOptions.map(opt => opt.value)
        });

        // Show feedback to the user if there was an invalid combination
        if (invalidMessage) {
            // Use setTimeout to ensure state is updated before showing the feedback
            setTimeout(() => {
                // Show a toast notification
                setToastTitle("Language Selection Updated");
                setToastMessage(invalidMessage);
                setToastEmoji("⚠️");
                setShowToast(true);
            }, 100);
        }
    }, [handleConfigChange]);

    // State for type dropdown
    const [selectedQuestionType, setSelectedQuestionType] = useState<DropdownOption>(questionTypeOptions[0]);
    const [selectedAnswerType, setSelectedAnswerType] = useState<DropdownOption>(answerTypeOptions[0]);
    const [selectedCodingLanguages, setSelectedCodingLanguages] = useState<DropdownOption[]>([codingLanguageOptions[0]]);

    // Update the selected options based on the current question's config
    useEffect(() => {
        if (questions.length > 0 && currentQuestionIndex >= 0 && currentQuestionIndex < questions.length) {
            const currentConfig = questions[currentQuestionIndex].config;

            // Set question type based on config
            setSelectedQuestionType(getQuestionTypeOption(currentConfig.questionType));

            // Set answer type based on config.inputType or default to 'text'
            setSelectedAnswerType(getAnswerTypeOption(currentConfig.inputType));

            // Set coding languages based on config.codingLanguages or default to first option
            if (currentConfig.codingLanguages && currentConfig.codingLanguages.length > 0) {
                const selectedLanguages = currentConfig.codingLanguages.map((langValue: string) => {
                    return codingLanguageOptions.find(opt => opt.value === langValue) || codingLanguageOptions[0];
                }).filter(Boolean);
                setSelectedCodingLanguages(selectedLanguages.length > 0 ? selectedLanguages : [codingLanguageOptions[0]]);
            } else {
                setSelectedCodingLanguages([]);
            }
        }
    }, [currentQuestionIndex, questions, getQuestionTypeOption, getAnswerTypeOption]);

    // Helper function to check if a scorecard is a published scorecard
    const isPublishedScorecard = (scorecardData: ScorecardTemplate): boolean => {
        // published scorecards are those that are already part of the school and fetched from api
        return scorecardData && !scorecardData.new && !scorecardData.is_template && typeof scorecardData.id === 'number';
    };

    const isUserCreatedNewScorecard = (scorecardData: ScorecardTemplate): boolean => {
        return scorecardData && !scorecardData.new && !scorecardData.is_template && typeof scorecardData.id === 'string';
    };

    const isLinkedScorecard = (scorecardData: ScorecardTemplate): boolean => {
        return isPublishedScorecard(scorecardData) || isUserCreatedNewScorecard(scorecardData);
    };

    // New function to sync all questions with a source scorecard when it changes
    const syncLinkedScorecards = useCallback((sourceId: string, newName?: string, newCriteria?: CriterionData[]) => {
        if (!sourceId) return;

        console.log("questions before:", questions);

        // Update all questions that have scorecard linked to this source
        const updatedQuestions = questions.map(question => {
            // Check if this question has a linked scorecard with the matching id
            // Only sync scorecards that are user-created (string id) and match the source id
            if (question.config.scorecardData &&
                typeof question.config.scorecardData.id === 'string' &&
                question.config.scorecardData.id === sourceId) {

                // Create an updated scorecard data
                const updatedScorecardData = {
                    ...question.config.scorecardData,
                    name: newName !== undefined ? newName : question.config.scorecardData.name,
                    criteria: newCriteria !== undefined ? newCriteria : question.config.scorecardData.criteria
                };

                // Return updated question with synced scorecard
                return {
                    ...question,
                    config: {
                        ...question.config,
                        scorecardData: updatedScorecardData
                    }
                };
            }

            // Return question unchanged if it doesn't have a matching scorecard
            return question;
        });

        console.log("Updated questions after:", updatedQuestions);

        // Update questions state and notify parent
        setQuestions(updatedQuestions);
        if (onChange) {
            onChange(updatedQuestions);
        }
    }, [questions, onChange]);

    return (
        <div className="flex flex-col h-full relative" key={`quiz-${taskId}-${isEditMode ? 'edit' : 'view'}`}>
            {/* Scorecard delete confirmation modal */}
            <ConfirmationDialog
                show={showScorecardDeleteConfirm && !isPreviewMode}
                title="Delete Scorecard"
                message="Are you sure you want to delete this scorecard? This action cannot be undone."
                onConfirm={() => {
                    removeScorecardFromSchoolScoreboards();
                    setShowScorecardDeleteConfirm(false);
                }}
                onCancel={() => setShowScorecardDeleteConfirm(false)}
                type="delete"
            />

            {/* Question delete confirmation modal */}
            <ConfirmationDialog
                show={showDeleteConfirm && !isPreviewMode}
                title="Delete Question"
                message="Are you sure you want to delete this question? This action cannot be undone."
                onConfirm={deleteQuestion}
                onCancel={() => setShowDeleteConfirm(false)}
                type="delete"
            />

            {/* Publish Confirmation Dialog */}
            <PublishConfirmationDialog
                show={showPublishConfirmation}
                title="Ready to publish?"
                message="After publishing, you won't be able to add or remove questions, but you can still edit existing ones"
                onConfirm={handleConfirmPublish}
                onCancel={handleCancelPublish}
                isLoading={isPublishing}
                errorMessage={publishError}
            />

            {/* Loading indicator */}
            {isLoadingQuestions && (
                <div className="absolute inset-0 bg-[#1A1A1A] bg-opacity-80 z-10 flex items-center justify-center">
                    <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-white"></div>
                </div>
            )}

            {/* Quiz Controls - Hide in preview mode and when there are no questions */}
            {!isPreviewMode && questions.length > 0 && (
                <div className="flex justify-between items-center mb-4 px-6 py-6">
                    {/* Left: Add Question Button */}
                    <div className="flex-1">
                        {!readOnly && status === 'draft' && <button
                            onClick={addQuestion}
                            className="flex items-center px-4 py-2 text-sm text-black bg-white hover:bg-gray-100 rounded-md transition-colors cursor-pointer"
                            disabled={readOnly}
                            style={{ opacity: readOnly ? 0.5 : 1 }}
                        >
                            <div className="w-5 h-5 rounded-full border border-black flex items-center justify-center mr-2">
                                <Plus size={12} className="text-black" />
                            </div>
                            Add Question
                        </button>}
                    </div>

                    {/* Middle: Navigation Controls */}
                    <div className="flex-1 flex items-center justify-center">
                        <button
                            onClick={goToPreviousQuestion}
                            disabled={currentQuestionIndex === 0}
                            className={`w-10 h-10 flex items-center justify-center rounded-full ${currentQuestionIndex === 0 ? 'text-gray-600 cursor-not-allowed' : 'text-gray-300 hover:text-white hover:bg-[#3A3A3A] cursor-pointer'} transition-colors border border-[#3A3A3A]`}
                            aria-label="Previous question"
                        >
                            <ChevronLeft size={20} />
                        </button>

                        <div className="mx-3 px-4 py-1.5 rounded-full border border-[#3A3A3A] bg-[#2A2A2A] text-gray-300 text-sm font-medium">
                            Question {currentQuestionIndex + 1} / {questions.length}
                        </div>

                        <button
                            onClick={goToNextQuestion}
                            disabled={currentQuestionIndex === questions.length - 1}
                            className={`w-10 h-10 flex items-center justify-center rounded-full ${currentQuestionIndex === questions.length - 1 ? 'text-gray-600 cursor-not-allowed' : 'text-gray-300 hover:text-white hover:bg-[#3A3A3A] cursor-pointer'} transition-colors border border-[#3A3A3A]`}
                            aria-label="Next question"
                        >
                            <ChevronRight size={20} />
                        </button>
                    </div>

                    {/* Right: Delete Button and Publish Button */}
                    <div className="flex-1 flex justify-end items-center space-x-3">
                        {!readOnly && status === 'draft' && (
                            <button
                                onClick={() => setShowDeleteConfirm(true)}
                                className="flex items-center px-3 py-1.5 text-sm text-red-400 hover:text-white bg-[#3A3A3A] hover:bg-red-600 rounded-md transition-colors cursor-pointer"
                                aria-label="Delete current question"
                            >
                                <Trash2 size={16} className="mr-1" />
                                Delete
                            </button>
                        )}
                    </div>
                </div>
            )}

            {/* Content area with animation when a new question is added */}
            <div className={`flex flex-1 gap-4 ${newQuestionAdded ? 'animate-new-question' : ''} ${isPreviewMode ? 'h-[600px]' : ''}`}>
                {isPreviewMode ? (
                    <>
                        <div
                            className="w-full h-full"
                            onClick={(e) => e.stopPropagation()} // Stop events from bubbling up
                            onMouseDown={(e) => e.stopPropagation()} // Stop mousedown events too
                        >
                            {MemoizedLearnerQuizView}

                        </div>
                    </>
                ) : (
                    <>
                        {questions.length === 0 ? (
                            <div className="w-full flex justify-center items-center">
                                <EmptyQuizPlaceholder />
                            </div>
                        ) : (
                            <div className="w-full flex flex-col mx-6 mb-4">
                                <div className="flex flex-col space-y-2 mb-4">

                                    <div className="flex items-center">
                                        <Dropdown
                                            icon={<HelpCircle size={16} />}
                                            title="Question Type"
                                            options={questionTypeOptions}
                                            selectedOption={selectedQuestionType}
                                            onChange={handleQuestionTypeChange}
                                            disabled={readOnly || status === 'published'}
                                            disabledTooltip={status === 'published' ? "Question type cannot be changed for published questions" : ""}
                                        />
                                    </div>
                                    {selectedQuestionType.value !== 'coding' ? (
                                        <div className="mb-4 flex items-center">
                                            <Dropdown
                                                icon={<Pen size={16} />}
                                                title="Answer Type"
                                                options={answerTypeOptions}
                                                selectedOption={selectedAnswerType}
                                                onChange={handleAnswerTypeChange}
                                                disabled={readOnly}
                                            />
                                        </div>
                                    ) : (
                                        <div className="mb-4 flex items-center">
                                            <div className={`w-full ${highlightedField === 'codingLanguage' ? 'outline outline-2 outline-red-400 shadow-md shadow-red-900/50 animate-pulse bg-[#2D1E1E] rounded-md' : ''}`}>
                                                <Dropdown
                                                    icon={<Pen size={16} />}
                                                    title="Languages"
                                                    options={codingLanguageOptions}
                                                    selectedOptions={selectedCodingLanguages}
                                                    onChange={handleCodingLanguageChange}
                                                    disabled={readOnly}
                                                    multiselect={true}
                                                    placeholder="Select one or more languages"
                                                />
                                            </div>
                                        </div>
                                    )}

                                </div>

                                {/* Segmented control for editor tabs */}
                                <div className="flex justify-center mb-4">
                                    <div className="inline-flex bg-[#222222] rounded-lg p-1">
                                        <button
                                            className={`flex items-center px-4 py-2 rounded-md text-sm font-medium cursor-pointer ${activeEditorTab === 'question'
                                                ? 'bg-[#333333] text-white'
                                                : 'text-gray-400 hover:text-white'
                                                }`}
                                            onClick={() => setActiveEditorTab('question')}
                                        >
                                            <HelpCircle size={16} className="mr-2" />
                                            Question
                                        </button>
                                        {selectedQuestionType.value !== 'subjective' ? (
                                            <button
                                                className={`flex items-center px-4 py-2 rounded-md text-sm font-medium cursor-pointer ${activeEditorTab === 'answer'
                                                    ? 'bg-[#333333] text-white'
                                                    : 'text-gray-400 hover:text-white'
                                                    }`}
                                                onClick={() => setActiveEditorTab('answer')}
                                            >
                                                <Check size={16} className="mr-2" />
                                                Correct Answer
                                            </button>
                                        ) : (
                                            <button
                                                className={`flex items-center px-4 py-2 rounded-md text-sm font-medium cursor-pointer ${activeEditorTab === 'scorecard'
                                                    ? 'bg-[#333333] text-white'
                                                    : 'text-gray-400 hover:text-white'
                                                    }`}
                                                onClick={() => setActiveEditorTab('scorecard')}
                                            >
                                                <ClipboardCheck size={16} className="mr-2" />
                                                Scorecard
                                            </button>
                                        )}
                                        <button
                                            className={`flex items-center px-4 py-2 rounded-md text-sm font-medium cursor-pointer ${activeEditorTab === 'knowledge'
                                                ? 'bg-[#333333] text-white'
                                                : 'text-gray-400 hover:text-white'
                                                }`}
                                            onClick={() => setActiveEditorTab('knowledge')}
                                        >
                                            <BookOpen size={16} className="mr-2" />
                                            AI Training Resources
                                        </button>
                                    </div>
                                </div>

                                <div className="w-full flex">
                                    {/* Show content based on active tab */}
                                    {activeEditorTab === 'question' ? (
                                        <div className="w-full">
                                            <div className={`editor-container h-[600px] overflow-y-auto overflow-hidden relative z-0 ${highlightedField === 'question' ? 'outline outline-2 outline-red-400 shadow-md shadow-red-900/50 animate-pulse bg-[#2D1E1E]' : ''}`}>
                                                <BlockNoteEditor
                                                    key={`quiz-editor-question-${currentQuestionIndex}`}
                                                    initialContent={currentQuestionContent}
                                                    onChange={handleQuestionContentChange}
                                                    isDarkMode={isDarkMode}
                                                    readOnly={readOnly}
                                                    onEditorReady={setEditorInstance}
                                                    className="quiz-editor"
                                                />
                                            </div>
                                        </div>
                                    ) : activeEditorTab === 'answer' ? (
                                        <div className={`w-full flex-1 bg-[#1A1A1A] rounded-md overflow-hidden h-[600px] overflow-y-auto ${highlightedField === 'answer' ? 'outline outline-2 outline-red-400 shadow-md shadow-red-900/50 animate-pulse bg-[#2D1E1E]' : ''}`}
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                // Ensure the correct answer editor keeps focus
                                                if (correctAnswerEditorRef.current) {
                                                    try {
                                                        // Try to focus the editor
                                                        correctAnswerEditorRef.current.focusEditor();
                                                    } catch (err) {
                                                        console.error("Error focusing correct answer editor:", err);
                                                    }
                                                }
                                            }}
                                            onMouseDown={(e) => {
                                                e.stopPropagation();
                                            }}
                                        >
                                            <BlockNoteEditor
                                                key={`correct-answer-editor-${currentQuestionIndex}`}
                                                initialContent={currentQuestionConfig.correctAnswer}
                                                onChange={handleCorrectAnswerChange}
                                                isDarkMode={isDarkMode}
                                                readOnly={readOnly}
                                                onEditorReady={setCorrectAnswerEditorInstance}
                                                className="correct-answer-editor"
                                                placeholder="Enter the correct answer here"
                                                allowMedia={false}
                                            />
                                        </div>
                                    ) : activeEditorTab === 'knowledge' ? (
                                        <div className="w-full mt-4 flex flex-row overflow-y-auto">
                                            {/* Left column with callout (20-30% width) */}
                                            <div className="w-[20%]">
                                                <div className="bg-[#222222] p-3 rounded-md">
                                                    <BookOpen size={16} className="text-amber-400 mb-2" />
                                                    <div>
                                                        <p className="text-gray-400 text-xs leading-tight mb-2">
                                                            These resources are <span className="font-bold text-white">optional</span> and will not be shown to learners but can be used by AI to provide more accurate and helpful feedback
                                                        </p>

                                                    </div>
                                                </div>
                                            </div>

                                            {/* Right column with linker and editor (70-80% width) */}
                                            <div className="w-[80%] flex flex-col">
                                                {readOnly &&
                                                    (!currentQuestion?.config?.linkedMaterialIds?.length &&
                                                        (!currentQuestion?.config?.knowledgeBaseBlocks?.length ||
                                                            extractTextFromBlocks(currentQuestion?.config?.knowledgeBaseBlocks || []).trim().length === 0)) ? (
                                                    <div className="w-full flex flex-col items-center justify-center p-8 text-center rounded-lg bg-[#1A1A1A] h-full">
                                                        <div className="max-w-md">
                                                            <h3 className="text-xl font-light text-white mb-3">No knowledge base found</h3>
                                                            <p className="text-gray-400 mb-6">
                                                                This question does not have any knowledge base attached to it
                                                            </p>
                                                        </div>
                                                    </div>
                                                ) : (
                                                    <div className="h-[600px]">
                                                        {/* Add learning material selection component */}
                                                        <div className="mb-4 ml-12">
                                                            <LearningMaterialLinker
                                                                courseId={courseId || ''}
                                                                linkedMaterialIds={currentQuestion?.config?.linkedMaterialIds || []}
                                                                readOnly={readOnly}
                                                                onMaterialsChange={(linkedMaterialIds) => {
                                                                    // Update the question config with the new linked material IDs
                                                                    const updatedQuestions = [...questions];
                                                                    const currentQuestion = updatedQuestions[currentQuestionIndex];
                                                                    const currentConfig = currentQuestion.config || {};

                                                                    updatedQuestions[currentQuestionIndex] = {
                                                                        ...currentQuestion,
                                                                        config: {
                                                                            ...currentConfig,
                                                                            linkedMaterialIds: linkedMaterialIds
                                                                        }
                                                                    };

                                                                    setQuestions(updatedQuestions);

                                                                    if (onChange) {
                                                                        onChange(updatedQuestions);
                                                                    }
                                                                }}
                                                            />
                                                        </div>

                                                        <div className="w-full flex-1 bg-[#1A1A1A] rounded-md overflow-hidden relative z-0"
                                                            onClick={(e) => {
                                                                e.stopPropagation();
                                                                // Ensure the knowledge base editor keeps focus
                                                                if (knowledgeBaseEditorRef.current) {
                                                                    try {
                                                                        // Try to focus the editor
                                                                        knowledgeBaseEditorRef.current.focusEditor();
                                                                    } catch (err) {
                                                                        console.error("Error focusing knowledge base editor:", err);
                                                                    }
                                                                }
                                                            }}
                                                            onMouseDown={(e) => {
                                                                e.stopPropagation();
                                                            }}
                                                        >
                                                            <BlockNoteEditor
                                                                key={`knowledge-base-editor-${currentQuestionIndex}`}
                                                                initialContent={currentQuestionConfig.knowledgeBaseBlocks || []}
                                                                onChange={(content) => {
                                                                    // Store blocks
                                                                    const updatedQuestions = [...questions];
                                                                    updatedQuestions[currentQuestionIndex] = {
                                                                        ...updatedQuestions[currentQuestionIndex],
                                                                        config: {
                                                                            ...updatedQuestions[currentQuestionIndex].config,
                                                                            knowledgeBaseBlocks: content
                                                                        }
                                                                    };
                                                                    setQuestions(updatedQuestions);

                                                                    if (onChange) {
                                                                        onChange(updatedQuestions);
                                                                    }
                                                                }}
                                                                isDarkMode={isDarkMode}
                                                                readOnly={readOnly}
                                                                onEditorReady={setKnowledgeBaseEditorInstance}
                                                                className="knowledge-base-editor"
                                                                placeholder="Link existing materials using the button above or add new material here"
                                                                allowMedia={false}
                                                            />
                                                        </div>
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    ) : (
                                        // Scorecard tab - show empty table if scorecard is selected, otherwise show placeholder
                                        currentQuestionConfig.scorecardData ? (
                                            <div className="h-[600px] overflow-y-auto w-full">
                                                <Scorecard
                                                    ref={scorecardRef}
                                                    name={currentQuestionConfig.scorecardData?.name || scorecardTitle}
                                                    criteria={currentQuestionConfig.scorecardData?.criteria || []}
                                                    onDelete={() => setShowScorecardDeleteConfirm(true)}
                                                    readOnly={status === 'published'}
                                                    linked={isLinkedScorecard(currentQuestionConfig.scorecardData)}
                                                    onNameChange={(newName) => {
                                                        if (!currentQuestionConfig.scorecardData) {
                                                            return;
                                                        }

                                                        const currentScorecardData = currentQuestionConfig.scorecardData;

                                                        // Update the title of the current scorecard
                                                        const updatedScorecardData = {
                                                            ...currentScorecardData,
                                                            name: newName
                                                        };

                                                        handleConfigChange({
                                                            scorecardData: updatedScorecardData
                                                        });

                                                        // Update the scorecard in schoolScorecards state
                                                        const updatedScorecards = schoolScorecards.map(sc =>
                                                            sc.id === currentScorecardData.id ? { ...sc, name: newName } : sc
                                                        );
                                                        setSchoolScorecards(updatedScorecards);

                                                        // If this is a source scorecard (created by user in this quiz),
                                                        // sync all linked scorecards to reflect the name change
                                                        if (currentScorecardData.new) {
                                                            syncLinkedScorecards(currentScorecardData.id, newName);
                                                        }
                                                    }}
                                                    onChange={(updatedCriteria) => {
                                                        if (!currentQuestionConfig.scorecardData) {
                                                            return;
                                                        }

                                                        const currentScorecardData = currentQuestionConfig.scorecardData;

                                                        // Update the current question's scorecard
                                                        const updatedScorecardData = {
                                                            ...currentScorecardData,
                                                            criteria: updatedCriteria
                                                        };

                                                        handleConfigChange({
                                                            scorecardData: updatedScorecardData
                                                        });

                                                        // Update the scorecard in schoolScorecards state
                                                        const updatedScorecards = schoolScorecards.map(sc =>
                                                            sc.id === currentScorecardData.id ? { ...sc, criteria: updatedCriteria } : sc
                                                        );
                                                        setSchoolScorecards(updatedScorecards);

                                                        // If this is a source scorecard (created by user in this quiz),
                                                        // sync all linked scorecards to reflect the criteria changes
                                                        if (currentScorecardData.new) {
                                                            syncLinkedScorecards(currentScorecardData.id, undefined, updatedCriteria);
                                                        }
                                                    }}
                                                />
                                            </div>
                                        ) : (
                                            <div className="w-full flex flex-col items-center justify-center p-8 text-center border border-dashed border-gray-700 rounded-lg bg-[#1A1A1A]">
                                                <div className="max-w-md">
                                                    <h3 className="text-xl font-light text-white mb-3">What is a scorecard?</h3>
                                                    <p className="text-gray-400 mb-6">
                                                        A scorecard is a set of parameters used to grade the answer to an open-ended question - either use one of our templates or create your own
                                                    </p>
                                                    <button
                                                        className="flex items-center px-5 py-2.5 text-sm text-black bg-white hover:bg-gray-100 rounded-md transition-colors cursor-pointer mx-auto"
                                                        ref={scorecardButtonRef}
                                                        onClick={handleOpenScorecardDialog}
                                                        disabled={readOnly}
                                                    >
                                                        <div className="w-5 h-5 rounded-full border border-black flex items-center justify-center mr-2">
                                                            <Plus size={12} className="text-black" />
                                                        </div>
                                                        Add a scorecard
                                                    </button>
                                                </div>
                                            </div>
                                        )
                                    )}
                                </div>
                            </div>
                        )}
                    </>
                )}
            </div>

            {/* Scorecard Templates Dialog */}
            <ScorecardPickerDialog
                key={`scorecard-picker-${schoolScorecards.length}`}
                isOpen={showScorecardDialog}
                onClose={() => setShowScorecardDialog(false)}
                onCreateNew={handleCreateNewScorecard}
                onSelectTemplate={handleSelectScorecardTemplate}
                position={scorecardDialogPosition || undefined}
                schoolScorecards={schoolScorecards}
            />

            {/* Toast for language combination validation */}
            <Toast
                show={showToast}
                title={toastTitle}
                description={toastMessage}
                emoji={toastEmoji}
                onClose={() => setShowToast(false)}
            />
        </div>
    );
});

export default QuizEditor;