import React, { useState, useRef, useEffect } from 'react';
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from '@/components/ui/command';
import {
    Type,
    Heading1,
    Heading2,
    Heading3,
    List,
    ListOrdered,
    CheckSquare,
    Minus,
    Mic
} from 'lucide-react';
import { BlockType } from '@/context/EditorContext';

interface BlockMenuProps {
    onSelectBlockType: (type: BlockType) => void;
    onClose: () => void;
    position: { top: number; left: number };
}

const blockTypes = [
    {
        label: 'Text',
        type: 'paragraph' as BlockType,
        icon: Type,
        description: 'Just start writing with plain text',
    },
    {
        label: 'Heading 1',
        type: 'heading1' as BlockType,
        icon: Heading1,
        description: 'Large section heading',
    },
    {
        label: 'Pranav 2',
        type: 'heading2' as BlockType,
        icon: Heading2,
        description: 'Medium section heading',
    },
    {
        label: 'Heading 3',
        type: 'heading3' as BlockType,
        icon: Heading3,
        description: 'Small section heading',
    },
    {
        label: 'Bullet List',
        type: 'bulletList' as BlockType,
        icon: List,
        description: 'Create a simple bullet list',
    },
    {
        label: 'Numbered List',
        type: 'numberedList' as BlockType,
        icon: ListOrdered,
        description: 'Create a numbered list',
    },
    {
        label: 'To-do List',
        type: 'todo' as BlockType,
        icon: CheckSquare,
        description: 'Track tasks with a to-do list',
    },
    {
        label: 'Divider',
        type: 'divider' as BlockType,
        icon: Minus,
        description: 'Create a visual divider',
    },
    {
        label: 'Voice Recorder',
        type: 'recorder' as BlockType,
        icon: Mic,
        description: 'Add a live voice recorder to your document',
    },
];

const BlockMenu: React.FC<BlockMenuProps> = ({ onSelectBlockType, onClose, position }) => {
    const [open, setOpen] = useState(true);
    const ref = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const handleOutsideClick = (event: MouseEvent) => {
            if (ref.current && !ref.current.contains(event.target as Node)) {
                setOpen(false);
                onClose();
            }
        };

        document.addEventListener('mousedown', handleOutsideClick);
        return () => {
            document.removeEventListener('mousedown', handleOutsideClick);
        };
    }, [onClose]);

    const handleSelect = (type: BlockType) => {
        onSelectBlockType(type);
        setOpen(false);
        onClose();
    };

    if (!open) return null;

    return (
        <div
            ref={ref}
            className="absolute bg-popover border border-border rounded-md shadow-md overflow-hidden z-10 mirror-content"
            style={{
                top: position.top,
                left: position.left,
                width: 240
            }}
        >
            <div className="py-2 mirror-content">
                <Command className="rounded-lg border border-border bg-card shadow-lg">
                    <CommandInput placeholder="Search for a block type..." />
                    <CommandList>
                        <CommandEmpty>No block type found.</CommandEmpty>
                        <CommandGroup heading="Block Types">
                            {blockTypes.map((blockType) => (
                                <CommandItem
                                    key={blockType.type}
                                    onSelect={() => handleSelect(blockType.type)}
                                    className="flex items-center py-2"
                                >
                                    <blockType.icon className="mr-2 h-4 w-4" />
                                    <div className="flex flex-col">
                                        <span>{blockType.label}</span>
                                        <span className="text-xs text-muted-foreground">
                                            {blockType.description}
                                        </span>
                                    </div>
                                </CommandItem>
                            ))}
                        </CommandGroup>
                    </CommandList>
                </Command>
            </div>
        </div>
    );
};

export default BlockMenu;
