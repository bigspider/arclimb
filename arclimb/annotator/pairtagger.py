#!/usr/bin/env python

import cv2
import numpy as np

from typing import List, Union, Callable, cast, NewType, Optional

# TODO(beisner): Decide if we should replace these with 'import *', since  they're getting a bit unruly
from PyQt5.QtCore import QPointF, QRectF, QLineF, QSize, QSizeF, Qt, pyqtSignal
from PyQt5.QtGui import QPolygonF, QPainterPath, QPainter, QPixmap, QWheelEvent, QMouseEvent, QCursor, QColor, QPen
from PyQt5.QtWidgets import QGraphicsItem, QGraphicsView, QSizePolicy, QGraphicsScene, QMenu, QAction, \
    QMessageBox, QInputDialog, QDialog, QVBoxLayout, QHBoxLayout, QButtonGroup, QPushButton, QApplication, \
    QFileDialog, QStyleOptionGraphicsItem, QWidget

from arclimb.core.correspondence import DoubleORBMatcher, CorrespondenceFinder
from arclimb.core.utils.image import scale_down_image
from arclimb.core import Point, Correspondence
from arclimb.core import HomographicPointMap

PointUnion = NewType('PointUnion', Union[Point, QPointF])


# noinspection PyPep8Naming
class BaseItem(QGraphicsItem):
    def __init__(self, imagePairEditor):
        super().__init__()

        self.imagePairEditor = imagePairEditor

    def getModel(self):
        raise NotImplemented("Subclasses of BaseItem should override getModel")

    def paint(self, painter: QPainter, option: 'QStyleOptionGraphicsItem', widget: Optional[QWidget] = None) -> None:
        pen = QPen(QColor('yellow'))
        pen.setCosmetic(True)
        painter.setPen(pen)

    # Returns a list of other items that should be deleted if this item is deleted.
    def getConnectedItems(self):
        return []


# noinspection PyPep8Naming
class PointItem(BaseItem):
    """
    QGraphicsItem representing one end of a correspondence.
    Except when the user is adding a new correspondence, each Node must be associated with exactly one Correspondence.

    """

    TYPE = QGraphicsItem.UserType + 1
    RADIUS = 4

    def type(self):
        return PointItem.TYPE

    def __init__(self, imagePairEditor: 'ImagePairEditor', model: Point, boundTo: QGraphicsItem):
        super().__init__(imagePairEditor)

        self.correspondenceItem = None

        self.boundToImg = boundTo

        self.model = model
        self._setPosFromModel(model)

        self.setCursor(Qt.PointingHandCursor)

        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations)
        self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)
        self.setZValue(1)

    def getModel(self):
        return self.model

    def _setPosFromModel(self, model: Point):
        p = model.toAbsoluteCoordinates(self.boundToImg.sceneBoundingRect())
        self.setPos(p.x, p.y)

    def _updateModel(self):
        self.model = Point(self.pos()).toRelativeCoordinates(self.boundToImg.sceneBoundingRect())

    def boundingRect(self):
        r = PointItem.RADIUS
        return QRectF(-r, -r, 2 * r, 2 * r)

    def shape(self):
        path = QPainterPath()
        path.addEllipse(self.boundingRect())
        return path

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        pen = painter.pen()

        if self.isSelected():
            pen.setWidth(2)

        painter.setPen(pen)
        painter.drawEllipse(self.boundingRect())

    # Returns the other endpoint of the associated CorrespondenceItem
    def getOtherEndpoint(self):
        src = self.correspondenceItem.getSourceNode()
        dst = self.correspondenceItem.getDestinationNode()
        return src if src != self else dst

    # If this item is removed, the CorrespondenceItem and its other endpoint should be removed
    def getConnectedItems(self):
        return [self.getCorrespondenceItem(), self.getOtherEndpoint()]

    def setCorrespondenceItem(self, corr: 'CorrespondenceItem'):
        self.correspondenceItem = corr
        corr.adjust()

    def getCorrespondenceItem(self) -> 'CorrespondenceItem':
        return self.correspondenceItem

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            # Constrain the position of the item
            rect = self.boundToImg.sceneBoundingRect()
            newPos = value
            if not rect.contains(newPos):
                newPos.setX(min(rect.right(), max(newPos.x(), rect.left())))
                newPos.setY(min(rect.bottom(), max(newPos.y(), rect.top())))
                return newPos
        elif change == QGraphicsItem.ItemPositionHasChanged:
            # Signal a change of position to the CorrespondenceItem and the editor
            self.correspondenceItem.adjust()
            self._updateModel()
        if change == QGraphicsItem.ItemSelectedHasChanged:
            # When a node is selected, also the CorrespondenceItem needs to update
            self.correspondenceItem.update()

        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.update()
        super().mouseReleaseEvent(event)


# noinspection PyPep8Naming,PyPep8Naming
class CorrespondenceItem(BaseItem):
    """
    QGraphicsItem representing a correspondence. Each Correspondence is associated with two Nodes.
    """

    TYPE = QGraphicsItem.UserType + 2

    def __init__(self, imagePairEditor, sourceNode: PointItem, destNode: PointItem):
        super().__init__(imagePairEditor)

        self.sourcePoint = QPointF()
        self.destPoint = QPointF()

        self.setAcceptedMouseButtons(Qt.NoButton)
        self.setCursor(Qt.ArrowCursor)

        self.sourceNode = sourceNode
        self.destinationNode = destNode
        self.sourceNode.setCorrespondenceItem(self)
        self.destinationNode.setCorrespondenceItem(self)
        self.adjust()

    def getModel(self) -> Correspondence:
        return Correspondence(self.sourceNode.getModel(), self.destinationNode.getModel())

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

        line = QLineF(self.mapFromItem(self.sourceNode, 0, 0), self.mapFromItem(self.destinationNode, 0, 0))

        self.prepareGeometryChange()

        self.sourcePoint = line.p1()
        self.destPoint = line.p2()
        self.update()

    def boundingRect(self):
        if not self.sourceNode or not self.destinationNode:
            return QRectF()

        return QRectF(self.sourcePoint,
                      QSizeF(self.destPoint.x() - self.sourcePoint.x(),
                             self.destPoint.y() - self.sourcePoint.y())).normalized()

    def shape(self):
        path = QPainterPath()
        polygon = QPolygonF()

        # Make sure that the line is a few pixels wide for interaction purposes
        polygon.append(self.sourcePoint + QPointF(2, 2))
        polygon.append(self.destPoint + QPointF(2, 2))
        polygon.append(self.destPoint - QPointF(2, 2))
        polygon.append(self.sourcePoint - QPointF(2, 2))
        path.addPolygon(polygon)
        return path

    def paint(self, painter: QPainter, option: 'QStyleOptionGraphicsItem', widget: Optional[QWidget] = ...) -> None:
        super().paint(painter, option, widget)

        assert self.sourceNode is not None and self.destinationNode is not None

        pen = painter.pen()

        if self.sourceNode.isSelected() or self.destinationNode.isSelected():
            pen.setStyle(Qt.DashLine)

        painter.setPen(pen)

        line = QLineF(self.sourcePoint, self.destPoint)
        painter.drawLine(line)

        # noinspection PyPep8Naming


# noinspection PyPep8Naming
class KeypointItem(BaseItem):
    """
    QGraphicsItem representing a KeyPoint. The GUI allows to replace a pair of KeyPointItems with a PointItem for
    convenience.
    """

    TYPE = QGraphicsItem.UserType + 3
    RADIUS = 4

    def type(self):
        return KeypointItem.TYPE

    def __init__(self, imagePairEditor: 'ImagePairEditor', position: Point, boundTo: QGraphicsItem):
        super().__init__(imagePairEditor)

        self.correspondenceItem = None

        self.position = position

        self.boundToImg = boundTo

        p = position.toAbsoluteCoordinates(boundTo.sceneBoundingRect())
        self.setPos(p.x, p.y)

        self.setCursor(Qt.PointingHandCursor)

        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations)
        self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)
        self.setZValue(1)

    def getModel(self):
        return None

    def boundingRect(self):
        r = KeypointItem.RADIUS
        return QRectF(-r, -r, 2 * r, 2 * r)

    def shape(self):
        path = QPainterPath()
        path.addEllipse(self.boundingRect())
        return path

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)

        # painter.setPen(QColor('green'))

        pen = painter.pen()
        if self.isSelected():
            pen.setWidth(2)

        painter.setPen(pen)
        painter.drawEllipse(self.boundingRect())

    def itemChange(self, change, value):
        # TODO: do we need this?
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.update()
        super().mouseReleaseEvent(event)


# noinspection PyPep8Naming
class GhostItem(BaseItem):
    """
    QGraphicsItem used to visualize the map of the current point in the other image, according to
    """

    TYPE = QGraphicsItem.UserType + 4
    RADIUS = 8

    def type(self):
        return GhostItem.TYPE

    def __init__(self, imagePairEditor: 'ImagePairEditor'):
        super().__init__(imagePairEditor)

        self.setFlag(QGraphicsItem.ItemIgnoresTransformations)

    def boundingRect(self):
        r = KeypointItem.RADIUS
        return QRectF(-r, -r, 2 * r, 2 * r)

    def shape(self):
        path = QPainterPath()
        path.addEllipse(self.boundingRect())
        return path

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        pen = painter.pen()

        pen.setColor(QColor(127, 255, 0))

        painter.setPen(pen)
        painter.drawEllipse(self.boundingRect())


# noinspection PyPep8Naming
class ImagePairEditor(QGraphicsView):
    MODE_SELECT = 1
    MODE_INSERT = 2
    MODE_DELETE = 3

    modeChanged = pyqtSignal(int)  # Emitted when mode changes

    def __init__(self, parent, image1: str, image2: str, correspondences: Optional[List[Correspondence]] = None):
        super().__init__(parent)

        self._zoom = 0

        self._insert_src = None
        self._insert_dst = None

        self.setCacheMode(QGraphicsView.CacheBackground)
        self.setViewportUpdateMode(QGraphicsView.BoundingRectViewportUpdate)
        self.setRenderHint(QPainter.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        self.setMinimumSize(QSize(1024, 768))

        scene = QGraphicsScene(self)
        scene.setItemIndexMethod(QGraphicsScene.NoIndex)
        self.setScene(scene)

        self._currentMode = None
        self.setMode(ImagePairEditor.MODE_SELECT)

        self._image1 = scene.addPixmap(QPixmap())
        self._image2 = scene.addPixmap(QPixmap())

        # Also open the images in OpenCV format, since converting between Mat and QImage is not trivial.
        # TODO: find a better way.
        self._image1_cv = cv2.imread(image1)
        self._image2_cv = cv2.imread(image2)

        self.setImages(image1, image2)

        if correspondences is not None:
            for corr in correspondences:
                self.addCorrespondence(corr)

        # Initialize ghost
        self._ghost = GhostItem(self)
        self.scene().addItem(self._ghost)
        self._ghost.hide()
        self._ghost_enabled = False

        self.fitToImages()

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

        self.fitToImages()

    def fitToImages(self):
        rect1 = QRectF(self._image1.pixmap().rect())
        self._image2.setX(rect1.width())
        rect2 = QRectF(self._image2.pixmap().rect())

        height = max(rect1.height(), rect2.height())
        width = rect1.width() + rect2.width()
        combined_rect = QRectF(QPointF(0, 0), QSizeF(width, height))
        self.setSceneRect(combined_rect)
        super().fitInView(combined_rect, Qt.KeepAspectRatio)

    def setImages(self, image1: str, image2: str):
        assert image1 is not None and image2 is not None

        self._zoom = 0
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self._image1.setPixmap(QPixmap(image1))
        self._image2.setPixmap(QPixmap(image2))
        self.fitToImages()

    def setGhostEnabled(self, enabled: bool = True) -> None:
        if self._ghost_enabled == enabled:
            return

        self._ghost_enabled = enabled
        if enabled:
            self._ghost_pointmap = HomographicPointMap(self.getCorrespondences())

            # TODO: handle if the PointMap fails to build

            self._updateGhostPosition()
        else:
            self._ghost.hide()

    def _updateGhostPosition(self):
        scenePos = self.mapToScene(self.mapFromGlobal(QCursor.pos()))
        pt = Point(scenePos).toRelativeCoordinates(self._image1.sceneBoundingRect())
        if 0 <= pt.x <= 1 and 0 <= pt.y <= 1:
            pt_mapped, _ = self._ghost_pointmap(pt)
            ghostScenePos = pt_mapped.toAbsoluteCoordinates(self._image2.sceneBoundingRect())

            self._ghost.setPos(ghostScenePos.x, ghostScenePos.y)
            self._ghost.show()
        else:
            # Cursor out of image1
            self._ghost.hide()

    def zoomFactor(self):
        return self._zoom

    def wheelEvent(self, event: QWheelEvent):
        # Unpack delta
        delta = event.angleDelta()
        delta = delta.x() + delta.y()

        if delta > 0:
            factor = 1.25
            self._zoom += 1
        else:
            factor = 0.8
            self._zoom -= 1

        if self._zoom > 0:
            self.scale(factor, factor)
        elif self._zoom == 0:
            self.fitToImages()
        else:
            self._zoom = 0

    def mousePressEvent(self, event: QMouseEvent):
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
        items = [cast(BaseItem, item) for item in items if isinstance(item, BaseItem)]

        image_rect = clicked_image.sceneBoundingRect()
        clickScenePos = self.mapToScene(event.pos())

        keypointItems = [x for x in items if isinstance(x, KeypointItem)]
        if len(keypointItems) > 0:
            # If a keypoint was clicked, adjust the coordinates of the click to its coordinates
            clickScenePos = keypointItems[0].pos()

        pt = Point(clickScenePos).toRelativeCoordinates(image_rect)

        if self.getMode() == ImagePairEditor.MODE_INSERT:
            if ((self._insert_src is not None and clicked_image == self._image1) or
                    (self._insert_dst is not None and clicked_image == self._image2)):
                return  # The node on this image was already inserted

            newNode = PointItem(self, model=pt, boundTo=clicked_image)
            self.scene().addItem(newNode)

            if clicked_image == self._image1:
                self._insert_src = newNode
            else:
                self._insert_dst = newNode

            # If both nodes are inserted, we add the edge and we are done
            if self._insert_src is not None and self._insert_dst is not None:
                self.scene().addItem(
                    CorrespondenceItem(self, cast(PointItem, self._insert_src), cast(PointItem, self._insert_dst)))
                self._insert_src = None
                self._insert_dst = None
        elif self.getMode() == ImagePairEditor.MODE_DELETE:
            # Delete all items overlapping with the cursor
            # TODO: implement stronger deletion tool (e.g.: delete all items in region around the cursor)
            for item in items:
                self.deleteItem(item)  # FIXME: this sometimes deletes an element twice, which upsets Qt

    def mouseMoveEvent(self, event: QMouseEvent):
        super().mouseMoveEvent(event)

        if self._ghost_enabled:
            self._updateGhostPosition()

    def contextMenuEvent(self, event):
        item = self.itemAt(event.pos())

        items_at_pos = self.items(event.pos())
        if self._image1 in items_at_pos:
            clicked_image = self._image1
            clicked_image_cv = self._image1_cv
        elif self._image2 in items_at_pos:
            clicked_image = self._image2
            clicked_image_cv = self._image2_cv
        else:
            return  # No context menu for clicks outside the image

        menu = QMenu(self)

        deleteAction = QAction("Delete this item", self)
        if isinstance(item, PointItem) or isinstance(item, CorrespondenceItem):
            menu.addAction(deleteAction)

        deleteAllItemsAction = QAction("Delete all items", self)
        menu.addAction(deleteAllItemsAction)

        autoFillAction = QAction("Autodetect matches", self)
        if item in [self._image1, self._image2]:
            menu.addAction(autoFillAction)

        computeAllKeypointsAction = QAction("Compute all keypoints", self)
        computeKeypointsAroundHereAction = QAction("Compute keypoints around here", self)
        removeKeypointAction = QAction("Remove this keypoint", self)
        removeAllKeypointsAction = QAction("Remove all keypoints", self)
        menu.addAction(computeAllKeypointsAction)
        menu.addAction(computeKeypointsAroundHereAction)
        if isinstance(item, KeypointItem):
            menu.addAction(removeKeypointAction)
        menu.addAction(removeAllKeypointsAction)

        action = menu.exec_(self.mapToGlobal(event.pos()))
        if action == deleteAction:
            self.deleteItem(item)
        elif action == deleteAllItemsAction:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Warning)

            msg.setText("Are you sure you want to delete all correspondences?\nThis cannot be undone.")
            msg.setWindowTitle("Confirm deletion")
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)

            retval = msg.exec_()
            if retval == QMessageBox.Yes:
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
        elif action == computeAllKeypointsAction:
            n_features, ok = QInputDialog.getInt(self, "Choose the number of keypoints.", "SIFT keypoints",
                                                 value=250, min=10, max=5000, step=50)

            if not ok:
                return

            # Delete any existing keypoint
            self.deleteAllItems(lambda it: isinstance(it, KeypointItem))

            img1 = scale_down_image(self._image1_cv)
            img2 = scale_down_image(self._image2_cv)

            img1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
            img2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)

            sift = cv2.xfeatures2d.SIFT_create(nfeatures=n_features)
            kp1, _ = sift.detectAndCompute(img1, None)
            kp2, _ = sift.detectAndCompute(img2, None)

            scene = self.scene()
            h1, w1, *_ = img1.shape
            for kp in kp1:
                pt = kp.pt
                scene.addItem(KeypointItem(self, position=Point(pt[0] / w1, pt[1] / h1), boundTo=self._image1))

            h2, w2, *_ = img2.shape
            for kp in kp2:
                pt = kp.pt
                scene.addItem(KeypointItem(self, position=Point(pt[0] / w2, pt[1] / h2), boundTo=self._image2))

        elif action == computeKeypointsAroundHereAction:
            n_features, ok = QInputDialog.getInt(self, "Choose the number of keypoints.", "SIFT keypoints",
                                                 value=500, min=10, max=5000, step=50)

            if not ok:
                return

            image_rect = clicked_image.sceneBoundingRect()
            clickScenePos = self.mapToScene(event.pos())

            pt = Point(clickScenePos).toRelativeCoordinates(image_rect)

            img = scale_down_image(clicked_image_cv)

            sift = cv2.xfeatures2d.SIFT_create(nfeatures=n_features)

            h, w, *_ = img.shape
            radius = min(w, h) / 10
            x_0, y_0 = pt.x * w, pt.y * h  # coordinates of the click

            # Only show keypoints around the click (radius roughly 1/10 of the image)
            mask = np.zeros([h, w], np.uint8)
            y, x = np.ogrid[0:h, 0:w]
            mask[(x - x_0) ** 2 + (y - y_0) ** 2 <= radius ** 2] = 255

            keypoints, _ = sift.detectAndCompute(img, mask)

            scene = self.scene()
            for kp in keypoints:
                pt = kp.pt
                scene.addItem(KeypointItem(self, position=Point(pt[0] / w, pt[1] / h), boundTo=clicked_image))

        elif action == removeKeypointAction:
            self.deleteItem(item)

        elif action == removeAllKeypointsAction:
            self.deleteAllItems(lambda it: isinstance(it, KeypointItem))

    # Deletes an item and the ones attached to it; if the item was removed already, don't do anything
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
                if condition is None or condition(item):
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
                for item in [BaseItem(it) for it in self.scene().selectedItems() if isinstance(it, BaseItem)]:
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
            self.setDragMode(QGraphicsView.ScrollHandDrag)
        elif mode == ImagePairEditor.MODE_INSERT:
            self.setDragMode(QGraphicsView.NoDrag)
            self.viewport().setCursor(Qt.CrossCursor)
        elif mode == ImagePairEditor.MODE_DELETE:
            # TODO
            self.setDragMode(QGraphicsView.NoDrag)
            self.viewport().setCursor(Qt.ForbiddenCursor)  # TODO: better custom cursor, maybe
            pass

        self.modeChanged.emit(mode)

    def getMode(self):
        return self._currentMode

    def getCorrespondences(self) -> List[Correspondence]:
        return [cast(CorrespondenceItem, item).getModel() for item in self.scene().items() if
                isinstance(item, CorrespondenceItem)]


# noinspection PyPep8Naming,PyUnresolvedReferences
class ImagePairEditorDialog(QDialog):
    def __init__(self, image1: str, image2: str, correspondences: Optional[List[Correspondence]] = None, parent=None):
        super().__init__(parent)

        self.editor = ImagePairEditor(self, image1, image2, correspondences)

        layout = QVBoxLayout()
        layout.addWidget(self.editor)

        buttons = QHBoxLayout()
        self.modeButtonGroup = QButtonGroup(self)

        self.selectButton = QPushButton("Select")
        self.selectButton.setCheckable(True)
        self.selectButton.setChecked(True)
        # self.selectButton.clicked.connect(self.selectButtonClicked)

        self.insertButton = QPushButton("Insert")
        self.insertButton.setCheckable(True)
        # self.insertButton.clicked.connect(self.insertButtonClicked)

        self.deleteButton = QPushButton("Delete")
        self.deleteButton.setCheckable(True)

        self.modeButtonGroup.addButton(self.selectButton, ImagePairEditor.MODE_SELECT)
        self.modeButtonGroup.addButton(self.insertButton, ImagePairEditor.MODE_INSERT)
        self.modeButtonGroup.addButton(self.deleteButton, ImagePairEditor.MODE_DELETE)
        # We use the mode as button id
        self.modeButtonGroup.buttonClicked[int].connect(lambda mode: self.editor.setMode(mode))
        self.editor.modeChanged.connect(self.modeChanged)

        self.ghostButton = QPushButton("Ghost")
        self.ghostButton.setCheckable(True)
        self.ghostButton.clicked.connect(self.ghostButtonClicked)

        okButton = QPushButton("OK")
        okButton.clicked.connect(self.okButtonClicked)
        cancelButton = QPushButton("Cancel")
        cancelButton.clicked.connect(self.cancelButtonClicked)

        buttons.addWidget(self.selectButton)
        buttons.addWidget(self.insertButton)
        buttons.addWidget(self.deleteButton)
        buttons.addSpacing(30)
        buttons.addWidget(self.ghostButton)
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

    def ghostButtonClicked(self):
        self.editor.setGhostEnabled(self.ghostButton.isChecked())

    def getCorrespondences(self):
        return self.editor.getCorrespondences()

    def keyPressEvent(self, event):
        # Let the editor handle all keypress events
        self.editor.keyPressEvent(event)

    # static method to create the dialog. Returns (accepted, [list of correspondences]
    @staticmethod
    def run(image1, image2, parent=None):
        dialog = ImagePairEditorDialog(image1, image2, parent)
        result = dialog.exec_()
        return dialog.getCorrespondences(), result == QDialog.Accepted


def run_gui():
    import sys

    app = QApplication(sys.argv)

    image_paths = []
    correspondences = []

    if len(sys.argv) >= 3:
        image_paths = sys.argv[1:3]
    else:
        while True:
            if len(image_paths) >= 2:
                break
            path_tup = QFileDialog.getOpenFileName(None, 'Choose an image')
            if path_tup:
                path, _ = path_tup
                image_paths.append(path)
            else:
                app.exit()

    corr, accepted = ImagePairEditorDialog.run(image_paths[0], image_paths[1], correspondences)
    print(corr)


if __name__ == '__main__':
    run_gui()
