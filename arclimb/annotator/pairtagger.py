from PyQt4 import QtCore, QtGui
from PyQt4.QtCore import Qt, pyqtSignal

from arclimb.core import Point, Correspondence

from typing import List, Union, Any, NewType, Callable

import cv2

from core.correspondence import DoubleORBMatcher, CorrespondenceFinder
from core.utils.image import scale_down_image

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
    def __init__(self, imagePairEditor):
        super().__init__()

        self.imagePairEditor = imagePairEditor

    def getModel(self):
        raise NotImplemented("Subclasses of BaseItem should override getModel")

    def paint(self, painter, option, widget):
        painter.setPen(QtGui.QColor('yellow'))

    #Returns a list of other items that should be deleted if this item is deleted.
    def getConnectedItems(self):
        return []


class PointItem(BaseItem):
    """
    QGraphicsItem representing one end of a correspondence.
    Except when the user is adding a new correspondence, each Node must be associated with exactly one Correspondence.

    """

    TYPE = QtGui.QGraphicsItem.UserType + 1
    RADIUS = 4

    def type(self):
        return PointItem.TYPE

    def __init__(self, imagePairEditor: 'ImagePairEditor', model: Point, boundTo: QtGui.QGraphicsItem):
        super().__init__(imagePairEditor)

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

    def shape(self):
        path = QtGui.QPainterPath()
        path.addEllipse(self.boundingRect());
        return path;

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        pen = painter.pen()
        pen.setCosmetic(True)

        if self.isSelected():
            pen.setWidth(2)

        painter.setPen(pen)
        painter.drawEllipse(self.boundingRect())

    # Returns the other endpoint of the associated CorrespondenceItem
    def getOtherEndpoint(self):
        src = self.correspondenceItem.getSourceNode()
        dst = self.correspondenceItem.getDestinationNode()
        return src if src != self else dst

    #If this item is removed, the CorrespondenceItem and its other endpoint should be removed
    def getConnectedItems(self):
        return [self.getCorrespondenceItem(), self.getOtherEndpoint()]

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
    QGraphicsItem representing a correspondence. Each Correspondence is associated with two Nodes.
    """

    TYPE = QtGui.QGraphicsItem.UserType + 2

    def __init__(self, imagePairEditor, sourceNode: PointItem, destNode: PointItem):
        super().__init__(imagePairEditor)

        self.sourcePoint = QtCore.QPointF()
        self.destPoint = QtCore.QPointF()

        self.setAcceptedMouseButtons(QtCore.Qt.NoButton)
        self.setCursor(Qt.ArrowCursor)

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

    # If this item is removed, the two endpoints should be removed
    def getConnectedItems(self):
        return [self.getSourceNode(), self.getDestinationNode()]

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

    def shape(self):
        path = QtGui.QPainterPath()
        polygon = QtGui.QPolygonF()

        #Make sure that the line is a few pixels wide for interaction purposes
        polygon.append(self.sourcePoint + QtCore.QPointF(2, 2))
        polygon.append(self.destPoint + QtCore.QPointF(2, 2))
        polygon.append(self.destPoint - QtCore.QPointF(2, 2))
        polygon.append(self.sourcePoint - QtCore.QPointF(2, 2))
        path.addPolygon(polygon);
        return path;

    def paint(self, painter: QtGui.QPainter, option, widget):
        super().paint(painter, option, widget)

        assert self.sourceNode is not None and self.destinationNode is not None

        pen = painter.pen()

        if self.sourceNode.isSelected() or self.destinationNode.isSelected():
            pen.setStyle(Qt.DashLine)

        painter.setPen(pen)

        line = QtCore.QLineF(self.sourcePoint, self.destPoint)
        painter.drawLine(line)

class KeypointItem(BaseItem):
    """
    QGraphicsItem representing a KeyPoint. The GUI allows to replace a pair of KeyPointItems with a PointItem for convenience.
    """

    TYPE = QtGui.QGraphicsItem.UserType + 3
    RADIUS = 4

    def type(self):
        return KeypointItem.TYPE

    def __init__(self, imagePairEditor: 'ImagePairEditor', position: Point, boundTo: QtGui.QGraphicsItem):
        super().__init__(imagePairEditor)

        self.correspondenceItem = None

        self.position = position

        self.boundToImg = boundTo

        p = _pointToAbsoluteCoordinates(position, boundTo.sceneBoundingRect())
        self.setPos(p.x, p.y)

        self.setCursor(Qt.PointingHandCursor)

        self.setFlag(QtGui.QGraphicsItem.ItemIsSelectable)
        self.setFlag(QtGui.QGraphicsItem.ItemSendsGeometryChanges)
        self.setFlag(QtGui.QGraphicsItem.ItemIgnoresTransformations)
        self.setCacheMode(QtGui.QGraphicsItem.DeviceCoordinateCache)
        self.setZValue(1)

    def getModel(self):
        return None

    def boundingRect(self):
        r = PointItem.RADIUS
        return QtCore.QRectF(-r, -r, 2 * r, 2 * r)

    def shape(self):
        path = QtGui.QPainterPath()
        path.addEllipse(self.boundingRect());
        return path;

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)

        #painter.setPen(QtGui.QColor('green'))

        pen = painter.pen()
        pen.setCosmetic(True)

        if self.isSelected():
            pen.setWidth(2)

        painter.setPen(pen)
        painter.drawEllipse(self.boundingRect())

    def itemChange(self, change, value):
        #TODO: do we need this?
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.update()
        super().mouseReleaseEvent(event)


class ImagePairEditor(QtGui.QGraphicsView):
    MODE_SELECT = 1
    MODE_INSERT = 2
    MODE_DELETE = 3

    modeChanged = pyqtSignal(int) # Emitted when mode changes

    def __init__(self, parent, image1: str, image2: str, correspondences: List[Correspondence] = []):
        super().__init__(parent)
        self._zoom = 0

        self._insert_src = None
        self._insert_dst = None

        self.setCacheMode(QtGui.QGraphicsView.CacheBackground)
        self.setViewportUpdateMode(QtGui.QGraphicsView.BoundingRectViewportUpdate)
        self.setRenderHint(QtGui.QPainter.Antialiasing)
        self.setTransformationAnchor(QtGui.QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QtGui.QGraphicsView.AnchorViewCenter)
        self.setSizePolicy(QtGui.QSizePolicy.MinimumExpanding, QtGui.QSizePolicy.MinimumExpanding)
        self.setMinimumSize(QtCore.QSize(1024, 768))

        scene = QtGui.QGraphicsScene(self)
        scene.setItemIndexMethod(QtGui.QGraphicsScene.NoIndex)
        self.setScene(scene)

        self._currentMode = None
        self.setMode(ImagePairEditor.MODE_SELECT)

        self._image1 = scene.addPixmap(QtGui.QPixmap())
        self._image2 = scene.addPixmap(QtGui.QPixmap())

        #Also open the images in OpenCV format, since converting between Mat and QImage is not trivial.
        # TODO: find a better way.
        self._image1_cv = cv2.imread(image1)
        self._image2_cv = cv2.imread(image2)

        self.setImages(image1, image2)

        for corr in correspondences:
            self.addCorrespondence(corr)

        self.fitInView()

    def addCorrespondence(self, corr: Correspondence):
        assert corr is not None
        scene = self.scene()
        node1 = PointItem(self, model=corr.point1, boundTo=self._image1)
        node2 = PointItem(self, model=corr.point2, boundTo=self._image2)
        scene.addItem(node1)
        scene.addItem(node2)
        scene.addItem(CorrespondenceItem(self, node1, node2))

    def showEvent(self, event):
        super().showEvent(event)

        self.fitInView()

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
        self._image1.setPixmap(QtGui.QPixmap(image1))
        self._image2.setPixmap(QtGui.QPixmap(image2))
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

        # We only handle left clicks
        if event.button() != Qt.LeftButton:
            return

        items = self.items(event.pos())
        if self._image1 in items:
            clicked_image = self._image1
        elif self._image2 in items:
            clicked_image = self._image2
        else:
            return

        # Only keep the BaseItems
        items = [item for item in items if isinstance(item, BaseItem)]

        image_rect = clicked_image.sceneBoundingRect()
        clickScenePos = self.mapToScene(event.pos())

        keypointItems = [x for x in items if isinstance(x, KeypointItem)]
        if len(keypointItems) > 0:
            # If a keypoint was clicked, adjust the coordinates of the click to its coordinates
            clickScenePos = keypointItems[0].pos()

        pt = _pointToRelativeCoordinates(clickScenePos, image_rect)

        if self.getMode() == ImagePairEditor.MODE_INSERT:
            if ((self._insert_src is not None and clicked_image == self._image1) or
                    (self._insert_dst is not None and clicked_image == self._image2)):
                return   # The node on this image was already inserted

            newNode = PointItem(self, model=pt, boundTo=clicked_image)
            self.scene().addItem(newNode)

            if clicked_image == self._image1:
                self._insert_src = newNode
            else:
                self._insert_dst = newNode

            # If both nodes are inserted, we add the edge and we are done
            if self._insert_src is not None and self._insert_dst is not None:
                self.scene().addItem(CorrespondenceItem(self, self._insert_src, self._insert_dst))
                self._insert_src = None
                self._insert_dst = None
        elif self.getMode() == ImagePairEditor.MODE_DELETE:
            # Delete all items overlapping with the cursor
            # TODO: implement stronger deletion tool (e.g.: delete all items in region around the cursor)
            for item in items:
                self.deleteItem(item) # FIXME: this sometimes deletes an element twice, which upsets Qt


    def contextMenuEvent(self, event):
        item = self.itemAt(event.pos());
        menu = QtGui.QMenu(self)

        deleteAction = QtGui.QAction("Delete this item", self)
        if type(item) in [PointItem, CorrespondenceItem]:
            menu.addAction(deleteAction)

        deleteAllItemsAction = QtGui.QAction("Delete all items", self)
        menu.addAction(deleteAllItemsAction)

        autoFillAction = QtGui.QAction("Autodetect matches", self)
        if item in [self._image1, self._image2]:
            menu.addAction(autoFillAction)

        showAllKeypointsAction = QtGui.QAction("Show all keypoints", self)
        removeKeypointAction = QtGui.QAction("Remove this keypoint", self)
        removeAllKeypointsAction = QtGui.QAction("Remove all keypoints", self)
        menu.addAction(showAllKeypointsAction)
        if type(item) == KeypointItem:
            menu.addAction(removeKeypointAction)
        menu.addAction(removeAllKeypointsAction)

        action = menu.exec_(self.mapToGlobal(event.pos()))
        if action == deleteAction:
            self.deleteItem(item)
        elif action == deleteAllItemsAction:
            msg = QtGui.QMessageBox()
            msg.setIcon(QtGui.QMessageBox.Warning)

            msg.setText("Are you sure you want to delete all correspondences?\nThis cannot be undone.")
            msg.setWindowTitle("Confirm deletion")
            msg.setStandardButtons(QtGui.QMessageBox.Yes | QtGui.QMessageBox.Cancel)

            retval = msg.exec_()
            if retval == QtGui.QMessageBox.Yes:
                self.deleteAllItems()
        elif action == autoFillAction:
            img1 = scale_down_image(self._image1_cv)
            img2 = scale_down_image(self._image2_cv)

            img1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
            img2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)

            corrFinder = CorrespondenceFinder(DoubleORBMatcher())
            correspondences = corrFinder.find_correspondences(img1, img2)

            for corr in correspondences:
                self.addCorrespondence(corr)
        elif action == showAllKeypointsAction:

            nfeatures, ok = QtGui.QInputDialog.getInt(self, "Choose the number of keypoints.", "SIFT keypoints",
                                      value=250, min=10, max=5000, step=50)

            if not ok:
                return

            #Delete any existing keypoint
            self.deleteAllItems(lambda x: type(x) == KeypointItem)

            img1 = scale_down_image(self._image1_cv)
            img2 = scale_down_image(self._image2_cv)

            # detect and add keypoints
            img1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
            img2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)

            sift = cv2.xfeatures2d.SIFT_create(nfeatures=nfeatures)
            kp1, _ = sift.detectAndCompute(img1, None)
            kp2, _ = sift.detectAndCompute(img2, None)

            scene = self.scene()
            h1, w1, *_ = img1.shape
            for kp in kp1:
                pt = kp.pt
                scene.addItem(KeypointItem(self, position=Point(pt[0]/w1, pt[1]/h1), boundTo=self._image1))

            h2, w2, *_ = img2.shape
            for kp in kp2:
                pt = kp.pt
                scene.addItem(KeypointItem(self, position=Point(pt[0]/w2, pt[1]/h2), boundTo=self._image2))

        elif action == removeKeypointAction:
            self.deleteItem(item)

        elif action == removeAllKeypointsAction:
            self.deleteAllItems(lambda x : type(x) == KeypointItem)

    #Deletes an item and the ones attached to it; if the item was removed already, don't do anything
    def deleteItem(self, item: BaseItem):
        to_remove = item.getConnectedItems()
        to_remove.append(item)

        scene = self.scene()
        for item in to_remove:
            scene.removeItem(item)

    def deleteAllItems(self, condition: Callable[[BaseItem], bool] = None):
        scene = self.scene()
        for item in scene.items():
            if isinstance(item, BaseItem):
                if condition is None or condition(item) == True:
                    scene.removeItem(item)

    def keyPressEvent(self, event):
        # If not in selection mode, Esc aborts and goes back to selection mode
        if self.getMode() != ImagePairEditor.MODE_SELECT:
            if event.key() == Qt.Key_Escape:
                self.setMode(ImagePairEditor.MODE_SELECT)
        else:
            # Selection mode
            # Cancel or backspace deletes all selected items
            if event.key() in [Qt.Key_Delete, Qt.Key_Backspace]:
                for item in self.scene().selectedItems():
                    self.deleteItem(item)

        # Prevent dialog from closing on escape
        if event.key() != Qt.Key_Escape:
            super().keyPressEvent(event)

    def setMode(self, mode):
        if self._currentMode == mode:
            return

        # Get out of current mode
        if self._currentMode == ImagePairEditor.MODE_SELECT:
            # Nothing to do here
            pass
        elif self._currentMode == ImagePairEditor.MODE_INSERT:
            if self._insert_src is not None:
                self.scene().removeItem(self._insert_src)
                self._insert_src = None
            if self._insert_dst is not None:
                self.scene().removeItem(self._insert_dst)
                self._insert_dst = None

                # TODO: scene items should be transparent to mouse events during insertion (and not draggable)
        elif self._currentMode == ImagePairEditor.MODE_DELETE:
            # TODO
            pass

        # Set up the new mode
        self._currentMode = mode
        if mode == ImagePairEditor.MODE_SELECT:
            self.setDragMode(QtGui.QGraphicsView.ScrollHandDrag)
        elif mode == ImagePairEditor.MODE_INSERT:
            self.setDragMode(QtGui.QGraphicsView.NoDrag)
            self.viewport().setCursor(Qt.CrossCursor)
        elif mode == ImagePairEditor.MODE_DELETE:
            # TODO
            self.setDragMode(QtGui.QGraphicsView.NoDrag)
            self.viewport().setCursor(Qt.ForbiddenCursor) # TODO: better custom cursor, maybe
            pass

        self.modeChanged.emit(mode)


    def getMode(self):
        return self._currentMode

    def getCorrespondences(self) -> List[Correspondence]:
        return [item.getModel() for item in self.scene().items() if type(item) == CorrespondenceItem]


class ImagePairEditorDialog(QtGui.QDialog):
    def __init__(self, image1: str, image2: str, correspondences: List[Correspondence] = [], parent = None):
        super().__init__(parent)

        self.editor = ImagePairEditor(self, image1, image2, correspondences)

        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.editor)

        buttons = QtGui.QHBoxLayout()
        self.modeButtonGroup = QtGui.QButtonGroup(self)


        self.selectButton = QtGui.QPushButton("Select")
        self.selectButton.setCheckable(True)
        self.selectButton.setChecked(True)
        #self.selectButton.clicked.connect(self.selectButtonClicked)

        self.insertButton = QtGui.QPushButton("Insert")
        self.insertButton.setCheckable(True)
        #self.insertButton.clicked.connect(self.insertButtonClicked)

        self.deleteButton = QtGui.QPushButton("Delete")
        self.deleteButton.setCheckable(True)

        self.modeButtonGroup.addButton(self.selectButton, ImagePairEditor.MODE_SELECT)
        self.modeButtonGroup.addButton(self.insertButton, ImagePairEditor.MODE_INSERT)
        self.modeButtonGroup.addButton(self.deleteButton, ImagePairEditor.MODE_DELETE)
        # We use the mode as button id
        self.modeButtonGroup.buttonClicked[int].connect(lambda id: self.editor.setMode(id))
        self.editor.modeChanged.connect(self.modeChanged)


        okButton = QtGui.QPushButton("OK")
        okButton.clicked.connect(self.okButtonClicked)
        cancelButton = QtGui.QPushButton("Cancel")
        cancelButton.clicked.connect(self.cancelButtonClicked)

        buttons.addWidget(self.selectButton)
        buttons.addWidget(self.insertButton)
        buttons.addWidget(self.deleteButton)
        buttons.addStretch(1)
        buttons.addWidget(okButton)
        buttons.addWidget(cancelButton)
        layout.addLayout(buttons)

        self.setLayout(layout)

    def modeChanged(self, mode):
        for btn in self.modeButtonGroup.buttons():
            btn.setChecked(self.modeButtonGroup.id(btn) == mode)

    def okButtonClicked(self):
        self.accept()

    def cancelButtonClicked(self):
        self.reject()

    def getCorrespondences(self):
        return self.editor.getCorrespondences()

    def keyPressEvent(self, event):
        # Let the editor handle all keypress events
        self.editor.keyPressEvent(event)

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

    image_paths = []
    correspondences = []

    if len(sys.argv) >= 3:
        image_paths = sys.argv[1:3]
    else:
        while True:
            if len(image_paths) >= 2:
                break
            path = QtGui.QFileDialog.getOpenFileName(None, 'Choose an image')
            if path:
                image_paths.append(path)
            else:
                sys.exit()


    corr, accepted = ImagePairEditorDialog.run(image_paths[0], image_paths[1], correspondences)
    print(corr)