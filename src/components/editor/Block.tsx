import React, { useRef, useEffect, KeyboardEvent } from 'react';
import { cn } from '@/lib/utils';
import { useEditor, BlockType } from '@/context/EditorContext';
import BlockControls from './BlockControls';

interface BlockProps {
    id: string;
    type: BlockType;
    content: string;
    onShowBlockMenu: (position: { top: number; left: number }, blockId: string) => void;
}

const Block: React.FC<BlockProps> = ({ id, type, content, onShowBlockMenu }) => {
    const {
        focusedBlockId,
        setFocusedBlockId,
        updateBlockContent,
        addBlock,
        deleteBlock,
        indentBlock,
        outdentBlock
    } = useEditor();

    // Use a generic ref type
    const blockRef = useRef<HTMLElement>(null);
    const isSelected = focusedBlockId === id;

    useEffect(() => {
        if (isSelected && blockRef.current) {
            blockRef.current.focus();

            // Place cursor at the end of the content
            const selection = window.getSelection();
            const range = document.createRange();

            if (selection && blockRef.current.firstChild) {
                range.selectNodeContents(blockRef.current);
                range.collapse(false);
                selection.removeAllRanges();
                selection.addRange(range);
            } else if (selection && !blockRef.current.firstChild) {
                blockRef.current.focus();
            }
        }
    }, [isSelected, id]);

    const handleFocus = () => {
        setFocusedBlockId(id);
    };

    const handleBlur = () => {
        // Keep the block id in context
        // We'll unset it only when clicking elsewhere
    };

    const handleInput = (e: React.FormEvent<HTMLElement>) => {
        // Get the current input text
        const newContent = e.currentTarget.textContent || '';
        console.log('Input received:', newContent);

        // Update the content in the editor context
        updateBlockContent(id, newContent);
    };

    const handleKeyDown = (e: KeyboardEvent<HTMLElement>) => {
        // Enter creates a new block
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            addBlock('paragraph', id);
            return;
        }

        // Backspace at the beginning removes the block
        if (e.key === 'Backspace' && (!content || content.length === 0)) {
            e.preventDefault();
            deleteBlock(id);
            return;
        }

        // Tab indents block
        if (e.key === 'Tab') {
            e.preventDefault();
            if (e.shiftKey) {
                outdentBlock(id);
            } else {
                indentBlock(id);
            }
            return;
        }

        // Show block menu on '/'
        if (e.key === '/' && !e.shiftKey && blockRef.current) {
            const selection = window.getSelection();
            if (selection && selection.rangeCount > 0) {
                const range = selection.getRangeAt(0);
                const rect = range.getBoundingClientRect();

                onShowBlockMenu({
                    top: rect.bottom + window.scrollY,
                    left: rect.left + window.scrollX
                }, id);

                e.preventDefault();
            }
        }
    };

    // Insert plus button handler
    const handlePlusButtonClick = () => {
        if (blockRef.current) {
            const rect = blockRef.current.getBoundingClientRect();
            onShowBlockMenu({
                top: rect.bottom + window.scrollY,
                left: rect.left + window.scrollX
            }, id);
        }
    };

    const getBlockElement = () => {
        const commonProps = {
            ref: blockRef as React.RefObject<any>,
            onInput: handleInput,
            onKeyDown: handleKeyDown,
            contentEditable: true,
            suppressContentEditableWarning: true,
            className: "outline-none"
        };

        // For debugging purposes, trace the content
        console.log(`Rendering block ${id} with content:`, content);

        switch (type) {
            case 'heading1':
                return (
                    <h1
                        {...commonProps}
                        className="mb-2 outline-none"
                        data-placeholder="Heading 1"
                    />
                );
            case 'heading2':
                return (
                    <h2
                        {...commonProps}
                        className="mb-2 outline-none"
                        data-placeholder="Heading 2"
                    />
                );
            case 'heading3':
                return (
                    <h3
                        {...commonProps}
                        className="mb-2 outline-none"
                        data-placeholder="Heading 3"
                    />
                );
            case 'bulletList':
                return (
                    <ul
                        {...commonProps}
                        className="list-disc pl-6 mb-2"
                    >
                        <li className="outline-none" data-placeholder="List item"></li>
                    </ul>
                );
            case 'numberedList':
                return (
                    <ol
                        {...commonProps}
                        className="list-decimal pl-6 mb-2"
                    >
                        <li className="outline-none" data-placeholder="List item"></li>
                    </ol>
                );
            case 'todo':
                return (
                    <div className="flex items-start gap-2 mb-2">
                        <input type="checkbox" className="mt-1.5 h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary" />
                        <div className="flex-1 outline-none" data-placeholder="To-do"></div>
                    </div>
                );
            case 'divider':
                return (
                    <div className="py-2">
                        <hr className="border-t border-border" />
                    </div>
                );
            case 'recorder':
                    return (
                        <div className="flex items-start gap-2 mb-2">
                        <input type="checkbox" className="mt-1.5 h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary" />
                        <div className="flex-1 outline-none" data-placeholder="To-do"></div>
                    </div>
                    );
            case 'paragraph':
            default:
                return (
                    <p
                        {...commonProps}
                        className="mb-2 outline-none"
                        data-placeholder="Start typing..."
                    />
                );
        }
    };

    // Ensure the content is properly set after render
    useEffect(() => {
        if (blockRef.current && blockRef.current.textContent !== content) {
            // Set textContent directly
            blockRef.current.textContent = content;
        }
    }, [content]);

    return (
        <div
            className={cn(
                "editor-block group relative px-3 py-1 rounded-md transition-all",
                isSelected && "focused"
            )}
            onFocus={handleFocus}
            onBlur={handleBlur}
        >
            {getBlockElement()}
            <BlockControls id={id} type={type} onPlusButtonClick={handlePlusButtonClick} />
        </div>
    );
};

export default Block;
