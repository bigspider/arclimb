from PyQt4 import QtCore, QtGui
from PyQt4.QtCore import Qt, pyqtSignal

from arclimb.core import Point, Correspondence

from typing import List, Union, Any, NewType


def _pointToRelativeCoordinates(pt: Union[Point, QtCore.QPointF], rect: QtCore.QRectF) -> Point:
    if type(pt) == QtCore.QPointF:
        pt = Point(pt.x(), pt.y())
    x = (pt.x - rect.x()) / rect.width()
    y = (pt.y - rect.y()) / rect.height()
    return Point(x, y)


def _pointToAbsoluteCoordinates(pt: Union[Point, QtCore.QPointF], rect: QtCore.QRectF) -> Point:
    if type(pt) == QtCore.QPointF:
        pt = Point(pt.x(), pt.y())
    return Point(rect.x() + rect.width() * pt.x, rect.y() + rect.height() * pt.y)


class BaseItem(QtGui.QGraphicsItem):
    def __init__(self):
        super().__init__()

    def getModel(self):
        raise NotImplemented("Subclasses of BaseItem should override getModel")

    def paint(self, painter, option, widget):
        painter.setPen(QtGui.QColor('yellow'))

class PointItem(BaseItem):
    """
    GraphicsItem representing one end of a correspondence.
    Except when the user is adding a new correspondence, each Node must be associated with exactly one Correspondence.

    """

    TYPE = QtGui.QGraphicsItem.UserType + 1
    RADIUS = 3

    def type(self):
        return PointItem.TYPE

    def __init__(self, imagePairEditor: 'ImagePairEditor', model: Point, boundTo: QtGui.QGraphicsItem):
        super().__init__()

        self.imagePairEditor = imagePairEditor
        self.correspondenceItem = None

        self.boundToImg = boundTo

        self.model = model
        self._setPosFromModel(model)

        self.setCursor(Qt.PointingHandCursor)

        self.setFlag(QtGui.QGraphicsItem.ItemIsMovable)
        self.setFlag(QtGui.QGraphicsItem.ItemIsSelectable)
        self.setFlag(QtGui.QGraphicsItem.ItemSendsGeometryChanges)
        self.setFlag(QtGui.QGraphicsItem.ItemIgnoresTransformations)
        self.setCacheMode(QtGui.QGraphicsItem.DeviceCoordinateCache)
        self.setZValue(1)

    def getModel(self):
        return self.model

    def _setPosFromModel(self, model: Point):
        p = _pointToAbsoluteCoordinates(model, self.boundToImg.sceneBoundingRect())
        self.setPos(p.x, p.y)

    def _updateModel(self):
        self.model = _pointToRelativeCoordinates(self.pos(), self.boundToImg.sceneBoundingRect())

    def boundingRect(self):
        r = PointItem.RADIUS
        return QtCore.QRectF(-r, -r, 2 * r, 2 * r)

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        pen = painter.pen()
        pen.setCosmetic(True)

        if self.isSelected():
            pen.setWidth(2)

        painter.setPen(pen)
        painter.drawEllipse(self.boundingRect())

    def setCorrespondenceItem(self, corr: 'CorrespondenceItem'):
        self.correspondenceItem = corr
        corr.adjust()

    def getCorrespondenceItem(self) -> 'CorrespondenceItem':
        return self.correspondenceItem

    def itemChange(self, change, value):
        if change == QtGui.QGraphicsItem.ItemPositionChange:
            #Constrain the position of the item
            rect = self.boundToImg.sceneBoundingRect()
            newPos = value
            if not rect.contains(newPos):
                newPos.setX(min(rect.right(), max(newPos.x(), rect.left())));
                newPos.setY(min(rect.bottom(), max(newPos.y(), rect.top())));
                return newPos;
        elif change == QtGui.QGraphicsItem.ItemPositionHasChanged:
            #Signal a change of position to the CorrespondenceItem and the editor
            self.correspondenceItem.adjust()
            self.imagePairEditor.itemMoved()
            self._updateModel()
        if change == QtGui.QGraphicsItem.ItemSelectedHasChanged:
            #When a node is selected, also the CorrespondenceItem needs to update
            self.correspondenceItem.update()


        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.update()
        super().mouseReleaseEvent(event)


class CorrespondenceItem(BaseItem):
    """
    GraphicsItem representing a correspondence. Each Correspondence is associated with two Nodes.
    """

    TYPE = QtGui.QGraphicsItem.UserType + 2

    def __init__(self, sourceNode: PointItem, destNode: PointItem):
        super().__init__()

        self.sourcePoint = QtCore.QPointF()
        self.destPoint = QtCore.QPointF()

        self.setAcceptedMouseButtons(QtCore.Qt.NoButton)

        self.sourceNode = sourceNode
        self.destinationNode = destNode
        self.sourceNode.setCorrespondenceItem(self)
        self.destinationNode.setCorrespondenceItem(self)
        self.adjust()

    def getModel(self) -> Correspondence:
        return Correspondence(self.sourceNode.getModel(), self.sourceNode.getModel())

    def getSourceNode(self) -> PointItem:
        return self.sourceNode

    def getDestinationNode(self) -> PointItem:
        return self.destinationNode

    def type(self):
        return CorrespondenceItem.TYPE

    def adjust(self):
        if not self.sourceNode or not self.destinationNode:
            return

        line = QtCore.QLineF(self.mapFromItem(self.sourceNode, 0, 0), self.mapFromItem(self.destinationNode, 0, 0))
        length = line.length()

        self.prepareGeometryChange()

        self.sourcePoint = line.p1()
        self.destPoint = line.p2()
        self.update()

    def boundingRect(self):
        if not self.sourceNode or not self.destinationNode:
            return QtCore.QRectF()

        return QtCore.QRectF(self.sourcePoint,
                QtCore.QSizeF(self.destPoint.x() - self.sourcePoint.x(),
                              self.destPoint.y() - self.sourcePoint.y())).normalized()

    def paint(self, painter: QtGui.QPainter, option, widget):
        super().paint(painter, option, widget)

        assert self.sourceNode is not None and self.destinationNode is not None

        pen = painter.pen()

        if self.sourceNode.isSelected() or self.destinationNode.isSelected():
            pen.setStyle(Qt.DashLine)

        painter.setPen(pen)

        line = QtCore.QLineF(self.sourcePoint, self.destPoint)
        painter.drawLine(line)


class ImagePairEditor(QtGui.QGraphicsView):
    def __init__(self, parent, image1, image2, correspondences: List[Correspondence] = []):
        super().__init__(parent)
        self._zoom = 0

        self._is_inserting = False
        self._insert_src = None
        self._insert_dst = None

        self.setCacheMode(QtGui.QGraphicsView.CacheBackground)
        self.setViewportUpdateMode(QtGui.QGraphicsView.BoundingRectViewportUpdate)
        self.setRenderHint(QtGui.QPainter.Antialiasing)
        self.setTransformationAnchor(QtGui.QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QtGui.QGraphicsView.AnchorViewCenter)
        self.setSizePolicy(QtGui.QSizePolicy.MinimumExpanding, QtGui.QSizePolicy.MinimumExpanding)
        self.setMinimumSize(QtCore.QSize(640, 480))

        scene = QtGui.QGraphicsScene(self)
        scene.setItemIndexMethod(QtGui.QGraphicsScene.NoIndex)
        scene.selectionChanged.connect(self.selectionChanged)
        self.setScene(scene)

        self._image1 = scene.addPixmap(QtGui.QPixmap())
        self._image2 = scene.addPixmap(QtGui.QPixmap())

        self.setImages(image1, image2)

        for corr in correspondences:
            self.addCorrespondence(corr)

        self.fitInView()

    def addCorrespondence(self, corr: Correspondence):
        scene = self.scene()
        node1 = PointItem(self, model=corr.point1, boundTo=self._image1)
        node2 = PointItem(self, model=corr.point2, boundTo=self._image2)
        scene.addItem(node1)
        scene.addItem(node2)
        scene.addItem(CorrespondenceItem(node1, node2))

    def showEvent(self, event):
        super().showEvent(event)

        self.fitInView()

    def itemMoved(self):
        pass
        #TODO: do we need this?

    def fitInView(self):
        rect1 = QtCore.QRectF(self._image1.pixmap().rect())
        self._image2.setX(rect1.width())
        rect2 = QtCore.QRectF(self._image2.pixmap().rect())

        heigth = max(rect1.height(), rect2.height())
        width = rect1.width() + rect2.width()
        combined_rect = QtCore.QRectF(QtCore.QPointF(0, 0), QtCore.QSizeF(width, heigth))
        self.setSceneRect(combined_rect)
        super().fitInView(combined_rect, Qt.KeepAspectRatio)

    def setImages(self, image1: QtGui.QPixmap, image2: QtGui.QPixmap):
        assert image1 is not None and image2 is not None

        self._zoom = 0
        self.setDragMode(QtGui.QGraphicsView.ScrollHandDrag)
        self._image1.setPixmap(image1)
        self._image2.setPixmap(image2)
        self.fitInView()

    def zoomFactor(self):
        return self._zoom

    def wheelEvent(self, event: QtGui.QWheelEvent):
        if event.delta() > 0:
            factor = 1.25
            self._zoom += 1
        else:
            factor = 0.8
            self._zoom -= 1
        if self._zoom > 0:
            self.scale(factor, factor)
        elif self._zoom == 0:
            self.fitInView()
        else:
            self._zoom = 0

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        super().mousePressEvent(event)

        items = self.items(event.pos())
        if self._image1 in items:
            clicked_image = self._image1
        elif self._image2 in items:
            clicked_image = self._image2
        else:
            return

        image_rect = clicked_image.sceneBoundingRect()
        scenePos = self.mapToScene(event.pos())
        pt = _pointToRelativeCoordinates(scenePos, image_rect)

        if self._is_inserting:
            if ((self._insert_src is not None and clicked_image == self._image1) or
                    (self._insert_dst is not None and clicked_image == self._image2)):
                return   # The node on this image was already inserted

            newNode = PointItem(self, model=pt, boundTo=clicked_image)
            self.scene().addItem(newNode)

            if clicked_image == self._image1:
                self._insert_src = newNode
            else:
                self._insert_dst = newNode

            #If both nodes are inserted, we add the edge and we are done
            if self._insert_src is not None and self._insert_dst is not None:
                self.scene().addItem(CorrespondenceItem(self._insert_src, self._insert_dst))
                self._insert_src = None
                self._insert_dst = None
                self.stopInsertion()

    def selectionChanged(self):
        print("Selection changed")

        print(self.scene().selectedItems())

    def keyPressEvent(self, event):
        if self._is_inserting:
            if event.key() == Qt.Key_Escape:
                self.stopInsertion()
        else:
            #Cancel or backspace deletes all selected items
            if event.key() in [Qt.Key_Delete, Qt.Key_Backspace]:
                to_remove = set() #list of Items to remove

                scene = self.scene()
                for item in scene.selectedItems():
                    if type(item) == PointItem:
                        #Also add the CorrespondenceItem and the other PointItem
                        item = item.getCorrespondenceItem()

                    if type(item) == CorrespondenceItem:
                        to_remove.add(item)
                        to_remove.add(item.getSourceNode())
                        to_remove.add(item.getDestinationNode())


                for item in to_remove:
                    scene.removeItem(item)

        if event.key() != Qt.Key_Escape: # prevent dialog from closing on escape
            super().keyPressEvent(event)


    def startInsertion(self):
        if self._is_inserting:
            return

        self._is_inserting = True

        self.setDragMode(QtGui.QGraphicsView.NoDrag)
        self.viewport().setCursor(Qt.CrossCursor)

        #TODO: scene items should be transparent to mouse events during insertion (and not draggable)

    def stopInsertion(self):
        if not self._is_inserting:
            return

        if self._insert_src is not None:
            self.scene().removeItem(self._insert_src)
            self._insert_src = None
        if self._insert_dst is not None:
            self.scene().removeItem(self._insert_dst)
            self._insert_dst = None

        self.setDragMode(QtGui.QGraphicsView.ScrollHandDrag)

        self._is_inserting = False

    def getCorrespondences(self) -> List[Correspondence]:
        return [item.getModel() for item in self.scene().items() if type(item) == CorrespondenceItem]


class ImagePairEditorDialog(QtGui.QDialog):
    def __init__(self, image1, image2, correspondences: List[Correspondence] = [], parent = None):
        super().__init__(parent)

        self.editor = ImagePairEditor(self, image1, image2, correspondences)

        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.editor)

        buttons = QtGui.QHBoxLayout()

        insertButton = QtGui.QPushButton("Insert")
        insertButton.clicked.connect(self.insertButtonClicked)

        okButton = QtGui.QPushButton("OK")
        okButton.clicked.connect(self.okButtonClicked)
        cancelButton = QtGui.QPushButton("Cancel")
        cancelButton.clicked.connect(self.cancelButtonClicked)

        buttons.addWidget(insertButton)
        buttons.addStretch(1)
        buttons.addWidget(okButton)
        buttons.addWidget(cancelButton)
        layout.addLayout(buttons)

        self.setLayout(layout)

    def insertButtonClicked(self):
        self.editor.startInsertion()

    def okButtonClicked(self):
        self.accept()

    def cancelButtonClicked(self):
        self.reject()

    def getCorrespondences(self):
        return self.editor.getCorrespondences()

    # static method to create the dialog. Returns (accepted, [list of correspondences]
    @staticmethod
    def run(image1, image2, parent = None):
        dialog = ImagePairEditorDialog(image1, image2, parent)
        result = dialog.exec_()
        return dialog.getCorrespondences(), result == QtGui.QDialog.Accepted


if __name__ == '__main__':

    import sys
    import random

    app = QtGui.QApplication(sys.argv)

    images = []
    correspondences = []

    #Some fake data
    #for path in ['/path/image1.jpg', '/path/image2.jpg']:
    #    images.append(QtGui.QPixmap(path))
    #correspondences = [Correspondence(Point(random.random(), random.random()), Point(random.random(), random.random())) for _ in range(4)]

    while True:
        if len(images) >= 2:
            break
        path = QtGui.QFileDialog.getOpenFileName(None, 'Choose an image')
        if path:
            images.append(QtGui.QPixmap(path))

    corr, accepted = ImagePairEditorDialog.run(images[0], images[1], correspondences)
    print(corr)