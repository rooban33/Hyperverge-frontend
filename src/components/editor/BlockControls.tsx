import React from 'react';
import {
    ChevronUp,
    ChevronDown,
    Trash2,
    Plus,
    MoreHorizontal,
    Type,
    Heading1,
    Heading2,
    Heading3,
    ListOrdered,
    List,
    CheckSquare,
    Minus
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { BlockType, useEditor } from '@/context/EditorContext';

interface BlockControlsProps {
    id: string;
    type: BlockType;
    onPlusButtonClick: () => void;
}

const BlockControls: React.FC<BlockControlsProps> = ({ id, type, onPlusButtonClick }) => {
    const {
        deleteBlock,
        moveBlockUp,
        moveBlockDown,
        updateBlockType
    } = useEditor();

    const handleAddBlock = (e: React.MouseEvent) => {
        e.stopPropagation();
        onPlusButtonClick();
    };

    const handleDeleteBlock = (e: React.MouseEvent) => {
        e.stopPropagation();
        deleteBlock(id);
    };

    const handleMoveUp = (e: React.MouseEvent) => {
        e.stopPropagation();
        moveBlockUp(id);
    };

    const handleMoveDown = (e: React.MouseEvent) => {
        e.stopPropagation();
        moveBlockDown(id);
    };

    const changeBlockType = (newType: BlockType) => {
        updateBlockType(id, newType);
    };

    return (
        <div
            className="block-controls absolute -left-10 top-1/2 -translate-y-1/2 flex flex-col gap-1 mirror-content"
        >
            <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 rounded-full hover:bg-muted hover:text-foreground mirror-content"
                onClick={handleAddBlock}
            >
                <Plus className="h-3 w-3" />
            </Button>

            <div className="flex flex-col gap-0.5">
                <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                        <Button
                            size="icon"
                            variant="ghost"
                            className="h-6 w-6 rounded-full bg-background shadow-sm hover:bg-secondary"
                        >
                            <MoreHorizontal className="h-3 w-3" />
                        </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="start" side="right" className="w-48 animate-scale-in">
                        <DropdownMenuLabel>Transform to</DropdownMenuLabel>
                        <DropdownMenuSeparator />

                        <DropdownMenuItem onClick={() => changeBlockType('paragraph')}>
                            <Type className="mr-2 h-4 w-4" />
                            <span>Text</span>
                        </DropdownMenuItem>

                        <DropdownMenuItem onClick={() => changeBlockType('heading1')}>
                            <Heading1 className="mr-2 h-4 w-4" />
                            <span>Heading 1</span>
                        </DropdownMenuItem>

                        <DropdownMenuItem onClick={() => changeBlockType('heading2')}>
                            <Heading2 className="mr-2 h-4 w-4" />
                            <span>Heading 2</span>
                        </DropdownMenuItem>

                        <DropdownMenuItem onClick={() => changeBlockType('heading3')}>
                            <Heading3 className="mr-2 h-4 w-4" />
                            <span>Heading 3</span>
                        </DropdownMenuItem>

                        <DropdownMenuItem onClick={() => changeBlockType('recorder')}>
                            <Heading3 className="mr-2 h-4 w-4"/>
                            <span>Voice Recorder</span>
                        </DropdownMenuItem>

                        <DropdownMenuItem onClick={() => changeBlockType('bulletList')}>
                            <List className="mr-2 h-4 w-4" />
                            <span>Bullet List</span>
                        </DropdownMenuItem>

                        <DropdownMenuItem onClick={() => changeBlockType('numberedList')}>
                            <ListOrdered className="mr-2 h-4 w-4" />
                            <span>Numbered List</span>
                        </DropdownMenuItem>

                        <DropdownMenuItem onClick={() => changeBlockType('todo')}>
                            <CheckSquare className="mr-2 h-4 w-4" />
                            <span>To-do List</span>
                        </DropdownMenuItem>


                        <DropdownMenuItem onClick={() => changeBlockType('divider')}>
                            <Minus className="mr-2 h-4 w-4" />
                            <span>Divider</span>
                        </DropdownMenuItem>

                        <DropdownMenuSeparator />

                        <DropdownMenuItem onClick={handleMoveUp} className="text-muted-foreground">
                            <ChevronUp className="mr-2 h-4 w-4" />
                            <span>Move up</span>
                        </DropdownMenuItem>

                        <DropdownMenuItem onClick={handleMoveDown} className="text-muted-foreground">
                            <ChevronDown className="mr-2 h-4 w-4" />
                            <span>Move down</span>
                        </DropdownMenuItem>

                        <DropdownMenuItem
                            onClick={handleDeleteBlock}
                            className="text-destructive focus:text-destructive"
                        >
                            <Trash2 className="mr-2 h-4 w-4" />
                            <span>Delete</span>
                        </DropdownMenuItem>
                    </DropdownMenuContent>
                </DropdownMenu>
            </div>
        </div>
    );
};

export default BlockControls;
